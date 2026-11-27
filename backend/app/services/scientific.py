"""Reproducible local scientific-product processing; acquisition is separate."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import numpy as np
from shapely.geometry import shape, mapping
from shapely.ops import unary_union


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Scientific timestamps require an explicit timezone')
    return result


def footprint(path, threshold, comparison='gte', baseline=None, percent=False):
    import rasterio
    from rasterio.features import shapes
    from rasterio.warp import transform_geom, reproject, Resampling
    if comparison not in ('gte', 'lte') or not np.isfinite(threshold):
        raise ValueError('Choose gte/lte and a finite threshold')
    if percent and not baseline:
        raise ValueError('Percent change requires a baseline raster')
    with rasterio.open(path) as raster:
        if raster.crs is None:
            raise ValueError('Raster requires an explicit CRS')
        if raster.width * raster.height > 16_000_000:
            raise ValueError('Crop the product to a study region (maximum 16 million pixels)')
        current = raster.read(1, masked=True).astype(float).filled(np.nan)
        transform, crs = raster.transform, raster.crs
        values = current.copy()
        if baseline:
            with rasterio.open(baseline) as before:
                if before.crs is None:
                    raise ValueError('Baseline raster requires a CRS')
                aligned = np.full(current.shape, np.nan)
                reproject(before.read(1, masked=True).astype(float).filled(np.nan), aligned,
                          src_transform=before.transform, src_crs=before.crs,
                          dst_transform=transform, dst_crs=crs, src_nodata=np.nan,
                          dst_nodata=np.nan, resampling=Resampling.bilinear)
                values = current - aligned
                if percent:
                    values = np.divide(values * 100, aligned, out=np.full_like(values,np.nan),
                                       where=np.isfinite(aligned) & (abs(aligned) > 1e-9))
        valid = np.isfinite(values)
        selected = valid & ((values >= threshold) if comparison == 'gte' else (values <= threshold))
        polygons = []
        for geometry, _ in shapes(selected.astype('uint8'), mask=selected, transform=transform):
            polygons.append(shape(transform_geom(crs, 'EPSG:4326', geometry)))
            if len(polygons) > 10000:
                raise ValueError('Footprint too fragmented; crop or preprocess the raster')
        geometry = mapping(unary_union(polygons)) if polygons else None
        return {'geometry': geometry, 'valid_pixels': int(valid.sum()), 'total_pixels': int(valid.size),
                'selected_pixels': int(selected.sum()), 'coverage_pct': round(float(valid.mean()*100),2),
                'minimum': float(values[valid].min()) if valid.any() else None,
                'maximum': float(values[valid].max()) if valid.any() else None,
                'mean': float(values[valid].mean()) if valid.any() else None,
                'threshold': threshold, 'comparison': comparison,
                'method': 'raster_difference_percent' if percent else 'raster_difference' if baseline else 'raster_threshold',
                'limitations': ['Threshold footprint is not an independently validated impact boundary.',
                                'Quality/cloud masks must be supplied as nodata by the product preprocessing.']}


def grid_to_geotiff(path, target, variable, selection=None):
    """Read an explicit 2-D regular lat/lon slice from NetCDF or GRIB."""
    import xarray as xr
    import rasterio
    from rasterio.transform import from_origin
    engine = 'cfgrib' if Path(path).suffix.lower() in ('.grib','.grb','.grib2') else None
    options = {'backend_kwargs': {'indexpath': ''}} if engine else {}
    with xr.open_dataset(path, engine=engine, **options) as dataset:
        if variable not in dataset:
            raise ValueError('Select a variable present in the dataset')
        array = dataset[variable]
        for dimension, index in (selection or {}).items():
            if dimension not in array.dims:
                raise ValueError(f'Unknown slice dimension: {dimension}')
            array = array.isel({dimension: int(index)})
        lat = next((name for name in ('latitude','lat') if name in array.dims), None)
        lon = next((name for name in ('longitude','lon') if name in array.dims), None)
        if not lat or not lon or set(array.dims) != {lat, lon}:
            raise ValueError('Explicitly select time, ensemble and level indices to produce a 2-D lat/lon slice')
        array = array.assign_coords({lon: (array[lon]+180)%360-180}).sortby(lon).sortby(lat, ascending=False)
        xs, ys = array[lon].values, array[lat].values
        if len(xs)<2 or len(ys)<2 or not np.allclose(np.diff(xs),xs[1]-xs[0]) or not np.allclose(np.diff(ys),ys[1]-ys[0]):
            raise ValueError('Only regular latitude/longitude grids are supported')
        if len(xs)*len(ys)>16_000_000:
            raise ValueError('Crop the product to a study region (maximum 16 million pixels)')
        if xs[1]-xs[0]>180:
            raise ValueError('Split a grid crossing the antimeridian into separate study areas')
        values = array.transpose(lat,lon).values.astype('float32')
        dx,dy = float(xs[1]-xs[0]),float(ys[0]-ys[1])
        with rasterio.open(target,'w',driver='GTiff',height=len(ys),width=len(xs),count=1,dtype='float32',
                           crs='EPSG:4326',transform=from_origin(float(xs[0])-dx/2,float(ys[0])+dy/2,dx,dy),nodata=np.nan) as output:
            output.write(values,1)
        return {'variable': variable, 'unit': str(array.attrs.get('units','unspecified')), 'selection': selection or {}}


def process(path, *, source, observed_at, provenance_url, threshold, comparison='gte',
            kind='observed', variable=None, selection=None, baseline=None, percent=False, published_at=None):
    from app.import_observations import parse_record
    if kind not in ('observed','forecast','derived','synthetic'):
        raise ValueError('Scientific kind must be observed, forecast, derived or synthetic')
    when=timestamp(observed_at)
    if not provenance_url.startswith(('https://','http://')):
        raise ValueError('Scientific imports require an attributed product URL')
    if kind=='forecast' and not published_at:raise ValueError('Forecast products require their published_at issue time')
    if published_at: timestamp(published_at)
    digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    metadata={}
    with tempfile.TemporaryDirectory() as tmp:
        raster=path
        if Path(path).suffix.lower() not in ('.tif','.tiff'):
            if not variable: raise ValueError('NetCDF/GRIB requires --variable and explicit nonspatial slices')
            raster=Path(tmp)/'slice.tif'
            metadata=grid_to_geotiff(path,raster,variable,selection)
        payload=footprint(raster,threshold,comparison,baseline,percent)
    payload.update(title=f'{source} scientific footprint',provenance_url=provenance_url,
                   product_sha256=digest,product_metadata=metadata,published_at=published_at,
                   hazard_kind='model_grid_threshold' if source=='glofas' else 'scientific_threshold',
                   input_classification=kind)
    if baseline:payload['baseline_sha256']=hashlib.sha256(Path(baseline).read_bytes()).hexdigest()
    key=hashlib.sha256(json.dumps([digest,payload,observed_at,kind],sort_keys=True).encode()).hexdigest()
    row={'external_id':key,'observed_at':when.isoformat(),'published_at':published_at,'kind':kind,'payload':payload}
    parse_record(row)
    return row
