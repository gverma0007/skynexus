"""Package only public cases, cached evaluations and synthetic fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
from app.services.historical import definitions, read_case, read_key, encoded
from app.services.historical_evaluation import METHOD_VERSION


def verify(destination=None):
    root = Path(destination) if destination else Path(__file__).parent / 'data' / 'hosted'
    manifest = json.loads((root / 'manifest.json').read_bytes())
    if manifest['method_version'] != METHOD_VERSION or len(manifest['cases']) != 8:
        raise ValueError('Historical release needs preparation for the current method')
    for item in manifest['files']:
        path = (root / item['key']).resolve()
        if not path.is_relative_to(root.resolve()):raise ValueError('Invalid release manifest key')
        content = path.read_bytes()
        if len(content) != item['size_bytes'] or hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('Historical release integrity check failed')
    return manifest


def prepare(destination):
    destination = Path(destination)
    files = {}
    catalogue = []
    for definition in definitions():
        ident = definition['id']
        data = read_case(ident)
        evaluation = json.loads(read_key(f'historical/evaluations/{ident}.json'))
        if evaluation.get('dataset_hash') != data['dataset_hash'] or evaluation.get('method_version') != METHOD_VERSION:
            raise ValueError(f'Recompute the evaluation for {ident} before packaging')
        files[f'historical/cases/{ident}.json'] = encoded(data)
        files[f'historical/evaluations/{ident}.json'] = encoded(evaluation)
        catalogue.append(dict(definition, dataset_mode='historical', status='available', download_supported=True,
            description=data['description'], cadence_hours=data['cadence_hours'], samples=len(data['times']),
            limitations=data['limitations'], domains=sorted({channel['domain'] for channel in data['channels']}),
            event_start=data['event_start'],event_end=data['event_end']))
        for source in data['provenance']:
            if source.get('name') == 'NAB license notice':
                files[source['archive_key']] = read_key(source['archive_key'])
    files['historical/catalogue.json'] = encoded(catalogue)
    from app.services.benchmark import dataset, run
    files['synthetic/dataset.json'] = encoded(dataset(42))
    files['synthetic/evaluation.json'] = encoded(run(42))
    manifest = {'method_version': METHOD_VERSION, 'cases': [row['id'] for row in definitions()], 'files': []}
    for key, content in sorted(files.items()):
        target = destination / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest['files'].append({'key': key, 'size_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    (destination / 'manifest.json').write_bytes(encoded(manifest))
    print(json.dumps({'cases': len(manifest['cases']), 'files': len(files), 'bytes': sum(len(value) for value in files.values())}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(Path(__file__).parent / 'data' / 'hosted'))
    prepare(parser.parse_args().output)
