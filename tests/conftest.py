# 테스트에서 각 스크립트 디렉터리를 import 경로에 올린다 (패키지 구조 없이 단일 파일 스크립트들이라서).
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ('', 'skill_detail/scripts', 'skill/scripts', 'realprice_서울구별',
            'skills/auction-priority-pipeline/scripts'):
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
