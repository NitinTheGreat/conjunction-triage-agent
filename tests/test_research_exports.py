import hashlib
import json

import pytest

from research.verify_exports import verify_bundle


@pytest.mark.parametrize('format', ['original', 'later'])
def test_export_check_preserves_exact_bytes_and_detects_newline_conversion(tmp_path, format):
    payload = b'name,value\r\nexample,1\r\n'
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path/'table.csv').write_bytes(payload)
    provenance = ({'runs': [{'artifacts': {'table.csv': {'sha256': digest}}}]}
                  if format == 'original' else {'artifacts': {'table.csv': digest}})
    (tmp_path/'provenance.json').write_text(json.dumps(provenance), encoding='utf-8')
    assert verify_bundle(tmp_path)['artifacts_verified'] == 1
    (tmp_path/'table.csv').write_bytes(payload.replace(b'\r\n', b'\n'))
    with pytest.raises(ValueError, match='checksum mismatch'):
        verify_bundle(tmp_path)
