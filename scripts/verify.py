#!/usr/bin/env python3
"""Offline verification of model, determinism, policy, and committed SVGs."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from public_data import validate, SECRET
from render import render_all
model=validate(json.loads((ROOT/'assets/generated/snapshot.json').read_text()))
for name,expected in render_all(model).items():
    actual=(ROOT/'assets/generated'/name).read_text()
    if actual!=expected:raise SystemExit(f'Artifact differs from deterministic render: {name}')
    root=ET.fromstring(actual)
    for node in root.iter():
        if node.tag.split('}')[-1] in {'script','foreignObject','image','a'}:raise SystemExit('Disallowed SVG element')
        for key,value in node.attrib.items():
            if key.startswith('on') or key.endswith('href'):raise SystemExit('Executable or external SVG content')
    if SECRET.search(actual):raise SystemExit('Credential-shaped asset content')
print('PASS: six deterministic, valid XML SVGs; public provenance and asset policy verified.')
