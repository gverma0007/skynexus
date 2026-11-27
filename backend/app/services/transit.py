"""Schedule matching for MBTA JSON:API and local standard GTFS feeds."""
import csv
from datetime import datetime, timedelta, timezone as datetime_timezone
import io
import zipfile
from zoneinfo import ZoneInfo


def mbta_delays(document, received_at):
    schedules={r['id']:r['attributes'] for r in document.get('included',[]) if r.get('type')=='schedule'}
    output=[]
    for row in document.get('data',[]):
        attributes=row.get('attributes',{})
        relationship=row.get('relationships',{}).get('schedule',{}).get('data')
        schedule=schedules.get(relationship.get('id')) if relationship else None
        if not schedule:continue
        # Match arrival to arrival (or departure to departure), never mix timestamps.
        field=next((key for key in ('arrival_time','departure_time') if attributes.get(key) and schedule.get(key)),None)
        if not field:continue
        predicted=datetime.fromisoformat(attributes[field].replace('Z','+00:00'))
        expected=datetime.fromisoformat(schedule[field].replace('Z','+00:00'))
        delay=(predicted-expected).total_seconds()
        route=row.get('relationships',{}).get('route',{}).get('data') or {}
        stop=row.get('relationships',{}).get('stop',{}).get('data') or {}
        output.append((f"{row['id']}:{received_at.isoformat()}",received_at,
                       {'entity_id':route.get('id','unknown_route'),'metric':'predicted_arrival_delay_seconds' if field=='arrival_time' else 'predicted_departure_delay_seconds',
                        'value':delay,'unit':'seconds','stop_id':stop.get('id'),'prediction_id':row['id'],
                        'scheduled_time':expected.isoformat(),'predicted_time':predicted.isoformat(),
                        'valid_time':predicted.isoformat(),'evidence_type':'provider_prediction_minus_matched_schedule',
                        'provenance_url':'https://api-v3.mbta.com/predictions',
                        'limitations':['Estimated delay from an upstream prediction, not an observed final arrival.']}))
    return output


def static_schedule(path, service_date):
    """Index a GTFS static ZIP for one explicit local service date."""
    with zipfile.ZipFile(path) as archive:
        def rows(name):
            if name not in archive.namelist():return []
            with archive.open(name) as source:
                return list(csv.DictReader(io.TextIOWrapper(source,encoding='utf-8-sig')))
        agencies=rows('agency.txt')
        timezone=ZoneInfo(agencies[0].get('agency_timezone','UTC')) if agencies else ZoneInfo('UTC')
        date=datetime.strptime(service_date,'%Y%m%d').date()
        weekday=('monday','tuesday','wednesday','thursday','friday','saturday','sunday')[date.weekday()]
        active={r['service_id'] for r in rows('calendar.txt') if r['start_date']<=service_date<=r['end_date'] and r.get(weekday)=='1'}
        for exception in rows('calendar_dates.txt'):
            if exception['date']==service_date:
                if exception['exception_type']=='1':active.add(exception['service_id'])
                else:active.discard(exception['service_id'])
        trips={r['trip_id']:r for r in rows('trips.txt') if r['service_id'] in active}
        result={}
        for row in rows('stop_times.txt'):
            if row['trip_id'] not in trips:continue
            item=dict(row,route_id=trips[row['trip_id']]['route_id'])
            for field in ('arrival_time','departure_time'):
                if not row.get(field):continue
                hours,minutes,seconds=map(int,row[field].split(':'))
                # GTFS defines elapsed service time relative to local noon minus twelve hours.
                origin=datetime.combine(date,datetime.min.time().replace(hour=12),timezone).astimezone(datetime_timezone.utc)-timedelta(hours=12)
                item[field]=(origin+timedelta(hours=hours,minutes=minutes,seconds=seconds)).astimezone(timezone)
            result[(row['trip_id'],int(row['stop_sequence']))]=item
        return result


def match_gtfs(feed_bytes, schedule_zip, service_date):
    from google.transit import gtfs_realtime_pb2
    from datetime import timezone
    feed=gtfs_realtime_pb2.FeedMessage();feed.ParseFromString(feed_bytes)
    received=datetime.fromtimestamp(feed.header.timestamp,timezone.utc)
    if not feed.header.timestamp:raise ValueError('GTFS realtime feed needs a publication timestamp')
    schedules=static_schedule(schedule_zip,service_date)
    output=[]
    for entity in feed.entity:
        if entity.is_deleted or not entity.HasField('trip_update'):continue
        update=entity.trip_update
        if update.trip.schedule_relationship==gtfs_realtime_pb2.TripDescriptor.CANCELED:continue
        if update.trip.start_date and update.trip.start_date!=service_date:continue
        for stop in update.stop_time_update:
            if stop.schedule_relationship in (gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.SKIPPED,gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.NO_DATA):continue
            schedule=schedules.get((update.trip.trip_id,stop.stop_sequence)) if stop.HasField('stop_sequence') else None
            if schedule is None and stop.stop_id:
                matches=[value for (trip,_),value in schedules.items() if trip==update.trip.trip_id and value['stop_id']==stop.stop_id]
                schedule=matches[0] if len(matches)==1 else None
            if not schedule:continue
            for field in ('arrival','departure'):
                if not stop.HasField(field) or field+'_time' not in schedule:continue
                event=getattr(stop,field)
                if event.HasField('time'):
                    delay=event.time-schedule[field+'_time'].timestamp()
                elif event.HasField('delay'):delay=event.delay
                else:continue
                output.append((f'{entity.id}:{stop.stop_sequence}:{field}:{feed.header.timestamp}',received,
                               {'entity_id':schedule['route_id'],'metric':f'predicted_{field}_delay_seconds','value':delay,'unit':'seconds',
                                'trip_id':update.trip.trip_id,'stop_id':schedule['stop_id'],'service_date':service_date,
                                'scheduled_time':schedule[field+'_time'].isoformat(),'evidence_type':'GTFS_realtime_schedule_match'}))
    return output
