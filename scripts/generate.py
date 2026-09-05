#!/usr/bin/env python3
"""Run with env -i PATH=... python3 -I scripts/generate.py --revision <sha>."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from public_data import AnonymousGitHub, collect, validate
from render import render_all

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--revision',required=True)
    parser.add_argument('--fixture',type=Path,help='Offline regeneration of a previously public snapshot; no publication authorization')
    args=parser.parse_args()
    now=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    model=json.loads(args.fixture.read_text()) if args.fixture else collect(AnonymousGitHub(),now,args.revision)
    validate(model)
    outputs=render_all(model)
    for svg in outputs.values():ET.fromstring(svg)
    outputs['snapshot.json']=json.dumps(model,indent=2,sort_keys=True)+'\n'
    target=ROOT/'assets/generated'
    target.mkdir(parents=True,exist_ok=True)
    # Stage everything before replacing any artifact. No partial output on API/policy failure.
    with tempfile.TemporaryDirectory(dir=target) as staging:
        for name,content in outputs.items(): (Path(staging)/name).write_text(content)
        for name,content in outputs.items():
            destination=target/name
            if not destination.exists() or destination.read_text()!=content:
                (Path(staging)/name).replace(destination)
    print(f"Validated {len(model['repositories'])} public repositories; rendered {len(outputs)-1} SVGs.")

if __name__=='__main__':main()
