"""Project completed legacy observation hours into durable research series."""
from datetime import datetime,timezone,timedelta
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from app.core.db import SessionLocal
from app.models.research import HourlyFeature,StreamEvent
from app.services.research import source_result


def projection_start(end,retention_days):
    # Never recompute an hour that retention can have partially pruned. Its
    # previously completed aggregate remains durable after the raw rows expire.
    return max(end-timedelta(days=30),end-timedelta(days=max(1,retention_days))+timedelta(hours=1))


def project():
    from app.core.config import get_settings
    end=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    start=projection_start(end,get_settings().RETENTION_DAYS)
    with SessionLocal() as db:
        flights=db.execute(text("""SELECT r.id::text,date_trunc('hour',f.timestamp),COUNT(DISTINCT f.icao24)
            FROM flight_observations f JOIN regions r ON ST_Contains(r.geom,f.position)
            WHERE f.source!='demo_dataset' AND f.timestamp>=:start AND f.timestamp<:end
            GROUP BY 1,2"""),{'start':start,'end':end}).all()
        weather=db.execute(text("""SELECT region_id::text,date_trunc('hour',timestamp),AVG(storm_index)
            FROM weather_observations WHERE source!='demo_dataset' AND timestamp>=:start AND timestamp<:end GROUP BY 1,2"""),{'start':start,'end':end}).all()
        counts={}
        for source,domain,metric,unit,rows in [('regional-aviation','aviation','aircraft_count','aircraft/hour',flights),('regional-weather','environment','storm_index','0-100 regional centre index',weather)]:
            count=0
            for entity,time,value in rows:
                statement=insert(HourlyFeature).values(source=source,domain=domain,entity=entity,metric=metric,unit=unit,timestamp=time,value_sum=float(value),sample_count=1)
                updated=db.execute(statement.on_conflict_do_update(constraint='uq_hourly_feature',set_={'value_sum':float(value),'sample_count':1,'updated_at':datetime.now(timezone.utc)},where=HourlyFeature.value_sum!=float(value)))
                count+=updated.rowcount
            counts[source]=count
            if count:source_result(db,source,count)
        db.commit()
    return counts
