#!/usr/bin/env python3
"""Verified, local-only draw.io stencil cache. This module never fetches URLs.

load_cache(path, viewer_bundle_sha256=None) returns an object exposing cache_id,
manifest_path, metadata and lookup(url). Nonmatching URLs return None. A matching
asset with invalid local evidence raises ValueError; it must not be served.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_HEX = re.compile(r'[0-9a-fA-F]{64}\Z')
_SEGMENT = re.compile(r'[A-Za-z0-9_.-]+\Z')


def _sha(value, label):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError(label + '_must_be_64_hex')
    return value.lower()


def _stencil_path(path):
    if not isinstance(path, str) or not path.startswith('/stencils/') or not path.endswith('.xml'):
        return None
    if '%' in path or '\\' in path or '?' in path or '#' in path:
        return None
    parts = path[len('/stencils/'):].split('/')
    if not parts or any(part in ('', '.', '..') or not _SEGMENT.fullmatch(part) for part in parts):
        return None
    return path


def _url_path(url):
    if not isinstance(url, str) or '%' in url or '?' in url or '#' in url or '\\' in url:
        return None
    # Whitespace/control normalization by urlsplit must not turn an invalid URL
    # into an approved one.
    if any(ord(char) <= 32 or ord(char) == 127 for char in url):
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc.lower() != 'viewer.diagrams.net'
                or parsed.username is not None or parsed.password is not None
                or parsed.port is not None or parsed.query or parsed.fragment):
            return None
        return _stencil_path(parsed.path)
    except ValueError:
        return None


def _relative_file(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('invalid_cache_file_relative_path')
    if value.startswith('/') or re.match(r'^[A-Za-z]:', value):
        raise ValueError('absolute_cache_file_path_disallowed')
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('cache_file_path_escape_or_empty_component')
    return tuple(parts)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_manifest_key')
        result[key] = value
    return result


class _NoDoctypeBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        # Parser callbacks also catch UTF-16/UTF-32 declarations, for which a
        # byte-substring scan alone would not detect the declaration.
        raise ValueError('stencil_doctype_disallowed')


def _verify_xml(body):
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('stencil_doctype_or_entity_disallowed')
    try:
        root = ET.fromstring(body, parser=ET.XMLParser(target=_NoDoctypeBuilder()))
    except (ET.ParseError, UnicodeError) as exc:
        raise ValueError('stencil_xml_parse_failed') from exc
    if not isinstance(root.tag, str):
        raise ValueError('stencil_xml_root_missing')
    if root.tag.rsplit('}', 1)[-1].lower() in ('html', 'head', 'body'):
        raise ValueError('html_is_not_stencil_xml')


def _read_local(root, parts, expected_bytes):
    """Open beneath the cache root with no symlink traversal, including races."""
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise ValueError('platform_lacks_required_nofollow_directory_support')
    descriptor = None
    try:
        descriptor = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        file_descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
        with os.fdopen(file_descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('cache_asset_is_not_regular_file')
            if info.st_size != expected_bytes:
                raise ValueError('cache_asset_size_mismatch')
            body = stream.read(expected_bytes + 1)
            if len(body) != expected_bytes:
                raise ValueError('cache_asset_size_changed_or_mismatch')
            return body
    except OSError as exc:
        raise ValueError('cache_asset_unreadable_or_symlink') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


class StencilCache:
    def __init__(self, manifest_path, manifest, assets):
        self.manifest_path = manifest_path
        self.cache_id = manifest['cache_id']
        # Metadata is evidence only; no root/version/URL is used to fetch data.
        self.metadata = {key: value for key, value in manifest.items() if key != 'assets'}
        self._root = manifest_path.parent.resolve()
        self._assets = assets
        self._verified = {}
        self._lock = threading.Lock()

    def lookup(self, url):
        path = _url_path(url)
        if path is None or path not in self._assets:
            return None
        with self._lock:
            if path not in self._verified:
                spec = self._assets[path]
                body = _read_local(self._root, spec['_parts'], spec['bytes'])
                digest = hashlib.sha256(body).hexdigest()
                if digest != spec['sha256']:
                    raise ValueError('cache_asset_sha256_mismatch')
                _verify_xml(body)
                self._verified[path] = (body, {
                    'url_path': path, 'sha256': digest, 'bytes': len(body),
                    'cache_file': spec['cache_file'],
                })
            body, evidence = self._verified[path]
            return {'body': body, 'content_type': 'application/xml', 'evidence': dict(evidence)}


def load_cache(manifest_path, viewer_bundle_sha256=None):
    path = Path(manifest_path).expanduser().absolute()
    if path.is_symlink():
        raise ValueError('manifest_symlink_disallowed')
    try:
        descriptor = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_MANIFEST_BYTES:
                raise ValueError('manifest_not_regular_or_over_4MB')
            body = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(body) > MAX_MANIFEST_BYTES:
            raise ValueError('manifest_over_4MB')
        manifest = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('cache_manifest_unreadable_or_invalid') from exc
    if not isinstance(manifest, dict):
        raise ValueError('cache_manifest_must_be_object')
    if not isinstance(manifest.get('cache_id'), str) or not manifest['cache_id'].strip():
        raise ValueError('cache_id_required')
    if viewer_bundle_sha256 is not None:
        expected = _sha(viewer_bundle_sha256, 'requested_viewer_bundle_sha256')
        actual = _sha(manifest.get('viewer_bundle_sha256'), 'manifest_viewer_bundle_sha256')
        if expected != actual:
            raise ValueError('viewer_bundle_sha256_mismatch')
    elif manifest.get('viewer_bundle_sha256') is not None:
        _sha(manifest['viewer_bundle_sha256'], 'manifest_viewer_bundle_sha256')
    entries = manifest.get('assets')
    if not isinstance(entries, dict):
        raise ValueError('cache_manifest_assets_must_be_object')
    assets = {}
    for url_path, entry in entries.items():
        if _stencil_path(url_path) != url_path:
            raise ValueError('invalid_stencil_manifest_url_path')
        if not isinstance(entry, dict):
            raise ValueError('cache_asset_spec_must_be_object')
        size = entry.get('bytes')
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError('cache_asset_bytes_must_be_nonnegative_integer')
        relative = entry.get('cache_file')
        assets[url_path] = {'cache_file': relative, '_parts': _relative_file(relative),
                            'sha256': _sha(entry.get('sha256'), 'cache_asset_sha256'), 'bytes': size}
    return StencilCache(path.resolve(), manifest, assets)


def self_test():
    def reject(operation):
        try:
            operation()
        except ValueError:
            return
        raise AssertionError('invalid input accepted')
    with tempfile.TemporaryDirectory(prefix='stencil-cache-fixture-') as directory:
        root = Path(directory)
        body = b'<?xml version="1.0"?><shapes><shape name="safe"/></shapes>'
        (root/'cache').mkdir()
        asset = root/'cache/aws4.xml'
        asset.write_bytes(body)
        viewer = '0c12ccf10dcaf0d0ef40ca60a5bc881ba27b57e076797ee39bce46602371f769'
        manifest = {'cache_id': 'fixture-v1', 'version': 'v32.6.1',
                    'commit': '84487-fixture', 'archive_sha256': '4'*64,
                    'viewer_bundle_sha256': viewer,
                    'assets': {'/stencils/aws4.xml': {'cache_file': 'cache/aws4.xml',
                               'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}}}
        path = root/'manifest.json'
        def write():path.write_text(json.dumps(manifest))
        write()
        cache = load_cache(path, viewer)
        url = 'https://viewer.diagrams.net/stencils/aws4.xml'
        result = cache.lookup(url)
        assert result['body'] == body and result['content_type'] == 'application/xml'
        assert result['evidence']['sha256'] == hashlib.sha256(body).hexdigest()
        assert cache.cache_id == 'fixture-v1' and cache.metadata['version'] == 'v32.6.1'
        for bad in ['http://viewer.diagrams.net/stencils/aws4.xml',
                    'https://evil.example/stencils/aws4.xml',
                    'https://user:pass@viewer.diagrams.net/stencils/aws4.xml',
                    'https://viewer.diagrams.net:443/stencils/aws4.xml',
                    url+'?token=secret', url+'?', url+'#fragment', url+'#',
                    'https://viewer.diagrams.net/stencils/%61ws4.xml',
                    'https://viewer.diagrams.net/stencils/../aws4.xml',
                    'https://viewer.diagrams.net/stencils//aws4.xml',
                    'https://viewer.diagrams.net/stencils/missing.xml']:
            assert cache.lookup(bad) is None, bad
        # Verified bytes are immutable even if a source file later changes.
        asset.write_bytes(body.replace(b'safe', b'evil'))
        assert cache.lookup(url)['body'] == body
        reject(lambda: load_cache(path, viewer).lookup(url))
        asset.write_bytes(body)
        reject(lambda: load_cache(path, 'f'*64))
        spec = manifest['assets']['/stencils/aws4.xml']
        spec['cache_file'] = '../escape.xml';write();reject(lambda: load_cache(path))
        spec['cache_file'] = str(asset);write();reject(lambda: load_cache(path))
        spec['cache_file'] = 'cache/link.xml';(root/'cache/link.xml').symlink_to(asset)
        write();reject(lambda: load_cache(path).lookup(url))
        (root/'alias').symlink_to(root/'cache', target_is_directory=True)
        spec['cache_file'] = 'alias/aws4.xml';write();reject(lambda: load_cache(path).lookup(url))
        for invalid in (b'<html><body>not XML stencils</body></html>',
                        b'<!DOCTYPE shapes [<!ENTITY x "bad">]><shapes>&x;</shapes>',
                        '<!DOCTYPE shapes [<!ENTITY x "bad">]><shapes>&x;</shapes>'.encode('utf-16')):
            asset.write_bytes(invalid);spec.update(cache_file='cache/aws4.xml',sha256=hashlib.sha256(invalid).hexdigest(),bytes=len(invalid));write()
            reject(lambda: load_cache(path).lookup(url))
        path.write_bytes(b' '*(MAX_MANIFEST_BYTES+1));reject(lambda: load_cache(path))
    print(json.dumps({'self_test':'passed','checks':['valid XML + immutable verified bytes','strict URL allowlist','SHA mismatch','viewer mismatch','relative-path containment','file and directory symlinks','HTML/DTD/entity including UTF-16','manifest size limit']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
    else:
        parser.error('--self-test required for standalone use')
