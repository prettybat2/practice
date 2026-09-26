# =========================================================
#  장면 3 (17–23초): 한 줄 → 삼각형으로 넓어지는 쐐기 → 3층 피라미드 붕괴
#  층 구조: 서 있는 도미노 줄 위에 눕힌 도미노(다리)를 걸치고, 그 위에 다음 층을 세움
#  실행: blender -b -P scripts/scene03_pyramid.py              (물리 검증)
#        blender -b -P scripts/scene03_pyramid.py -- render 1 60
# =========================================================
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAMES = 200
scene = D.reset_scene(frames=FRAMES, time_scale=2.5)
D.wood_floor()

H, T = D.DOM_H, D.DOM_T
GAP = 0.6             # 줄 간격 (y)
COL = 0.51            # 옆 칸 간격 (x) — 도미노 폭 0.5, 눕힌 판 하나(길이 1.0)가 두 칸을 덮음
ROWS = 6              # 피라미드 앞뒤 줄 수
COLS = [6, 4, 2]      # 층별 칸 수 (아래 → 위): 앞에서 보면 피라미드
EPS = 0.003           # 층 사이 살짝 띄움 (처음 겹침 방지)
FLAT_FRICTION = 0.6
YAW = 0.0             # +y 방향으로 쓰러짐

standing, flats = [], []
FLAT_MAT = D.plastic_mat((0.96, 0.93, 0.85))           # 흰 송편색 가로판


def flat_domino(x, y, z, name):
    """눕힌 도미노: 길이(1.0)가 x(옆) 방향, 폭이 y, 두께가 위아래.
    같은 줄의 두 칸만 묶으므로 줄 전체가 함께 앞으로 넘어갈 수 있다."""
    mesh = D._domino_mesh(1.0)
    o = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(o)
    o.location = (x, y, z + T / 2)
    o.rotation_euler = (math.radians(90), 0, math.radians(90))
    o.material_slots[0].link = 'OBJECT'
    o.material_slots[0].material = FLAT_MAT
    D.add_rigid(o, 'ACTIVE', mass=D.DOM_MASS, friction=FLAT_FRICTION, bounce=0.02)
    return o


# ---------- 들어오는 줄 + 쐐기(1→6칸) ----------
N_WEDGE = COLS[0] - 1          # 1~5칸 줄, 그다음이 피라미드 첫 줄(6칸)
lead = []
for m in range(6, 0, -1):
    lead.append(D.make_domino((0, -GAP * (N_WEDGE + m), 0), YAW, 1.0, D.rainbow(0.0), f'Lead_{m}'))
D.lean(lead[0])
wedge = []
for k in range(N_WEDGE):
    for i in range(k + 1):
        x = (i - k / 2) * COL
        wedge.append(D.make_domino((x, GAP * (k - N_WEDGE), 0), YAW, 1.0,
                                   D.rainbow(0.03 + 0.07 * k), f'Wedge_{k}_{i}'))

# ---------- 피라미드 ----------
z = 0.0
for lv, ncol in enumerate(COLS):
    xs = [(i - (ncol - 1) / 2) * COL for i in range(ncol)]
    for j in range(ROWS):
        for i, x in enumerate(xs):
            if lv < 2:
                rgb = D.rainbow(0.4 + 0.45 * j / (ROWS - 1) + 0.03 * lv)   # 줄마다 초록→보라
            else:
                rgb = (0.95, 0.72, 0.2)                                     # 꼭대기는 금색
            standing.append(D.make_domino((x, GAP * j, z), YAW, 1.0, rgb, f'P{lv}_{j}_{i}'))
    z += H + EPS
    if lv < len(COLS) - 1:
        for j in range(ROWS):                       # 각 줄 위에 두 칸씩 덮는 가로판
            for i in range(0, ncol, 2):
                fx = (xs[i] + xs[i + 1]) / 2
                flats.append(flat_domino(fx, GAP * j, z, f'F{lv}_{j}_{i}'))
        z += T + EPS

# ---------- 빠져나가는 줄 (다음 장면으로) ----------
exit_line = [D.make_domino((0, GAP * (ROWS + m), 0), YAW, 1.0, D.rainbow(0.6 + 0.04 * m), f'Exit_{m}')
             for m in range(8)]

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
D.camera(loc=(7.5, -6.5, 5.0), target=(0, 1.2, 1.2), lens=30, dof_fstop=None)
D.render_setup(scene, preview=True)

allstand = lead + wedge + standing + exit_line
print(f'서 있는 도미노 {len(allstand)}개, 눕힌 다리판 {len(flats)}개, 꼭대기 높이 {z:.2f}')

# 처음 몇 프레임 동안 구조물이 제자리에 서 있는지 (저절로 무너지지 않는지)
scene.frame_set(1)
p0 = {o.name: o.matrix_world.translation.copy() for o in standing + flats}
scene.frame_set(20)
drift = max((o.matrix_world.translation - p0[o.name]).length for o in standing + flats
            if not o.name.startswith('P0_0'))
print(f'  20프레임 동안 피라미드 최대 흔들림: {drift:.4f}')

D.verify(scene, allstand, every=20)
fl_down = sum(1 for f in flats if f.matrix_world.translation.z < 0.5)
print(f'  바닥까지 떨어진 다리판: {fl_down}/{len(flats)}')

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene03_f{f:03d}.png'))
