"""Print capability and credential status without displaying secret values."""
import json
from app.core.config import get_settings

CAPABILITIES = {
    'Native vessel streaming': ('AISSTREAM_API_KEY',),
    'NASA fire acquisition': ('FIRMS_MAP_KEY',),
    'Air-quality acquisition': ('OPENAQ_API_KEY',),
    'Electricity acquisition': ('EIA_API_KEY',),
    'Cloudflare connectivity': ('CLOUDFLARE_API_TOKEN',),
    'Historical maritime events': ('GFW_API_TOKEN',),
    'Copernicus EWDS acquisition': ('EWDS_API_TOKEN',),
    'Authenticated flight allowance': ('OPENSKY_CLIENT_ID','OPENSKY_CLIENT_SECRET'),
    'Higher transit allowance (optional)': ('MBTA_API_KEY',),
    'AI narrative (optional)': ('ANTHROPIC_API_KEY','ANTHROPIC_MODEL'),
    'R2 archival (optional)': ('R2_ENDPOINT_URL','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET'),
}

def status():
    cfg=get_settings()
    return [{'capability':name,'configured':all(bool(getattr(cfg,key,'')) for key in keys),
             'required_variables':list(keys),'missing_variables':[key for key in keys if not getattr(cfg,key,'')]} for name,keys in CAPABILITIES.items()]

if __name__=='__main__':print(json.dumps({'local_features_need_provider_keys':False,'storage_backend':get_settings().ARCHIVE_STORAGE,'capabilities':status()},indent=2))
