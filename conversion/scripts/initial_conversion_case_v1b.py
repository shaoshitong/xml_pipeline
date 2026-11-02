"""Lossless page text-dictionary bytes adapter for frozen initial case v1.

Only page[0-9]+_text.json is adapted. Compilation, PDF captures and native
XML/PNG generation run the frozen v1 functions without replacement.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import initial_conversion_case_v1 as frozen

MARKER='__external_binary_asset_v1__'
ORIGINAL_WRITE_JSON=frozen.write_json


def externalize_page_dictionary(value,path):
    path=Path(path).resolve();work=path.parent;floor=(frozen.R/frozen.OWNER).resolve()
    if not work.is_relative_to(floor) or not re.fullmatch(r'page[0-9]+_text\.json',path.name):raise ValueError('Binary adapter requires an owned page text dictionary')
    directory=work/'page_dictionary_binary_v1'/path.stem
    def walk(item):
        if isinstance(item,bytes):
            digest=hashlib.sha256(item).hexdigest();destination=directory/(digest+'.bin');directory.mkdir(parents=True,exist_ok=True)
            if not directory.resolve().is_relative_to(work):raise ValueError('Binary assets directory escaped owned case')
            if destination.exists():
                if destination.read_bytes()!=item:raise ValueError('Immutable page dictionary binary asset differs')
            else:
                with destination.open('xb') as stream:stream.write(item);stream.flush();os.fsync(stream.fileno())
            return {MARKER:{'type':'bytes','file':str(destination.relative_to(frozen.R)),'sha256':digest,'length':len(item)}}
        if isinstance(item,dict):
            if any(not isinstance(key,str) for key in item):raise TypeError('Page dictionary keys must be strings')
            return {key:walk(content) for key,content in item.items()}
        if isinstance(item,(list,tuple)):return [walk(content) for content in item]
        if item is None or isinstance(item,(str,bool,int,float)):return item
        raise TypeError('Unknown page dictionary JSON value: '+type(item).__name__)
    return walk(value)


def restore_page_dictionary(value,work):
    work=Path(work).resolve();floor=(frozen.R/frozen.OWNER).resolve()
    if not work.is_relative_to(floor):raise ValueError('Restore requires an owned case workspace')
    def walk(item):
        if isinstance(item,dict):
            if set(item)=={MARKER}:
                descriptor=item[MARKER]
                if set(descriptor)!={'type','file','sha256','length'} or descriptor['type']!='bytes':raise ValueError('Unknown binary descriptor')
                path=(frozen.R/descriptor['file']).resolve()
                if not path.is_relative_to(work/'page_dictionary_binary_v1'):raise ValueError('Binary descriptor outside owned page dictionary assets')
                raw=path.read_bytes()
                if len(raw)!=descriptor['length'] or hashlib.sha256(raw).hexdigest()!=descriptor['sha256']:raise ValueError('Binary descriptor hash/length mismatch')
                return raw
            return {key:walk(content) for key,content in item.items()}
        if isinstance(item,list):return [walk(content) for content in item]
        return item
    return walk(value)


def write_json(path,value):
    path=Path(path)
    if re.fullmatch(r'page[0-9]+_text\.json',path.name):value=externalize_page_dictionary(value,path)
    return ORIGINAL_WRITE_JSON(path,value)


def main(request_path):
    previous=frozen.write_json;frozen.write_json=write_json
    try:return frozen.main(request_path)
    finally:frozen.write_json=previous


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('request');args=parser.parse_args();main(args.request)
