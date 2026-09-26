# =========================================================
#  장면 2 (10–17초): 커지는 무지개 S자 → 크게 돌아 → 계단 오르기
#                   → 다리 위에서 자기 줄 앞부분을 건너 교차 → 계단 내려가기
#  실행: blender -b -P scripts/scene02_stairs_bridge.py              (물리 검증)
#        blender -b -P scripts/scene02_stairs_bridge.py -- render 1 120
# =========================================================
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAMES = 360
scene = D.reset_scene(frames=FRAMES, time_scale=2.5)
D.wood_floor()
STAIR_MAT = D.simple_mat('LacquerWood', (0.35, 0.08, 0.05), rough=0.3, coat=0.6)
TREAD_MAT = D.simple_mat('TreadWood', (0.55, 0.36, 0.2), rough=0.4, coat=0.3)
BRASS = D.simple_mat('Brass', (0.85, 0.62, 0.3), rough=0.25, metal=1.0)

# ---------- 계단·다리 치수 ----------
TREAD = 0.57          # 계단 한 칸 = 도미노 간격(크기 1.0일 때 0.6보다 살짝 촘촘)
RISE = 0.2            # 한 칸 높이 (도미노 높이의 1/5)
N_UP, N_DECK, N_DOWN = 7, 3, 7
Y_BRIDGE = -1.5
X0 = TREAD * (N_UP + 1)          # 다리 가운데 칸이 x=0 (아래 줄이 지나가는 곳)
DECK_H = RISE * N_UP

# ---------- 바닥 경로 (계단 전까지) ----------
X_END = X0 + TREAD                       # 바닥 마지막 도미노 자리
R2 = 1.5
X_RIGHT = X_END + R2
R1 = X_RIGHT / 2
def wiggle(n=300):
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(Vector((0.9 * math.sin(2 * math.pi * t) * math.sin(math.pi * t), -0.5 + 5.5 * t, 0)))
    return pts
floor_path = D.polyline(
    D.straight((0, -6.5), (0, -0.5)),                       # 곧게: 다리 밑을 지나감
    wiggle(),                                                # S자
    D.arc((R1, 5.0), R1, math.pi, 0),                        # 크게 오른쪽으로 U턴
    D.straight((X_RIGHT, 5.0), (X_RIGHT, 0)),
    D.arc((X_END, 0), R2, 0, -math.pi / 2),                  # 다리 쪽으로 꺾기
)
plan = D.plan_along(floor_path, scale_fn=lambda u: 0.7 + 0.3 * min(u / 0.85, 1.0), align_end=True)

# ---------- 계단 위 도미노 자리 ----------
heights = ([RISE * (i + 1) for i in range(N_UP)] + [DECK_H] * N_DECK +
           [DECK_H - RISE * (i + 1) for i in range(N_DOWN)])
yaw_mx = math.atan2(1, 0)       # -x 방향으로 쓰러짐
for i, h in enumerate(heights):
    x = X0 - TREAD * i
    plan.append((Vector((x, Y_BRIDGE, h)), yaw_mx, 1.0, 1.0))
# 내려와서 바닥으로 이어지는 꼬리
x_last = X0 - TREAD * (len(heights) - 1)
for k in range(1, 8):
    plan.append((Vector((x_last - TREAD * k, Y_BRIDGE, 0)), yaw_mx, 1.0, 1.0))

dominoes = D.build_plan(plan, prefix='S2')
D.lean(dominoes[0])

# ---------- 계단·다리 구조물 ----------
DEPTH = 0.9
for i, h in enumerate(heights):
    x = X0 - TREAD * i
    if h <= 0:
        continue
    if N_UP <= i < N_UP + N_DECK:
        # 다리 상판: 아래가 비어 있어야 아래 줄이 지나감
        D.box(f'Deck_{i}', (x, Y_BRIDGE, h - 0.05), (TREAD, DEPTH, 0.1), TREAD_MAT)
    else:
        D.box(f'Step_{i}', (x, Y_BRIDGE, h / 2), (TREAD, DEPTH, h), STAIR_MAT)
# 다리 난간 기둥 (장식)
for sx in (-1, 1):
    for sy in (-1, 1):
        D.box(f'Post_{sx}_{sy}', (sx * TREAD * 1.5, Y_BRIDGE + sy * (DEPTH / 2 + 0.04), DECK_H + 0.3),
              (0.06, 0.06, 0.6), BRASS, physics=False)
for sy in (-1, 1):
    D.box(f'Rail_{sy}', (0, Y_BRIDGE + sy * (DEPTH / 2 + 0.04), DECK_H + 0.58),
          (TREAD * 3 + 0.06, 0.05, 0.05), BRASS, physics=False)

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
D.camera(loc=(1.5, -14.0, 11.0), target=(1.6, 1.0, 0.0), lens=24, dof_fstop=None)
D.render_setup(scene, preview=True)

print(f'도미노 {len(dominoes)}개 (계단·다리 {len(heights)}개 포함)')
D.verify(scene, dominoes, every=30)

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene02_f{f:03d}.png'))
