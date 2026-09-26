#!/bin/bash
# 클라우드 미리보기용: 장면 클립을 차례로 만듦
cd "$(dirname "$0")"
for s in scene01 scene02 scene03 scene04 scene05 scene06 scene07; do
  DOMINO_PREVIEW_CPU=1 python3 -u make_clips.py -- $s || echo "실패: $s"
done
