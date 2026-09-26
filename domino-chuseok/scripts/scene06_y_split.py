# =========================================================
#  장면 6 (36–42초): Y자 분기 → 두 갈래가 계단을 올라 → 받침대 위 송편 구슬 두 개를 밀어냄
#  → 구슬이 경사로를 타고 벽 쪽(장면 7)으로 굴러감. 좌우 대칭이라 두 구슬이 동시에 출발.
#  실행: blender -b -P scripts/scene06_y_split.py              (물리 검증)
#        blender -b -P scripts/scene06_y_split.py -- render 1 90
# =========================================================
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAMES = 160
scene = D.reset_scene(frames=FRAMES, time_scale=2.5)
D.wood_floor()
STAIR_MAT = D.simple_mat('LacquerWood', (0.35, 0.08, 0.05), rough=0.3, coat=0.6)
TREAD_MAT = D.simple_mat('TreadWood', (0.55, 0.36, 0.2), rough=0.4, coat=0.3)
BRASS = D.simple_mat('Brass', (0.85, 0.62, 0.3), rough=0.25, metal=1.0)

GAP = 0.6
Y_SPLIT = 0.0
SPLIT_ANG = math.radians(22)       # 갈래 첫 도미노가 벌어지는 각
BR_X = 3.0                          # 갈래가 도착하는 x (좌우 대칭)
BR_LEN = 5.0                        # 갈래 길이 (y 방향)
TREAD, RISE, N_UP = 0.57, 0.2, 6
R_BALL = 0.3
RAMP_L = 4.5

# ---------- 몸통 줄 ----------
trunk = D.dominoes_along(D.straight((0, -6.0, 0), (0, Y_SPLIT, 0), n=100),
                         color_fn=lambda u: D.rainbow(0.72 + 0.12 * u),
                         prefix='Trunk', align_end=True)
D.lean(trunk[0])


def hermite(p0, t0, p1, t1, n=300):
    out = []
    for i in range(n + 1):
        s = i / n
        h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
        h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
        out.append(p0 * h00 + t0 * h10 + p1 * h01 + t1 * h11)
    return out


def branch(side, colors, name):
    """side=-1 왼쪽, +1 오른쪽. 갈래 도미노 + 계단 + 받침대 + 구슬 + 경사로."""
    p0 = Vector((side * 0.27, Y_SPLIT + 0.52, 0))
    t0 = Vector((side * math.sin(SPLIT_ANG), math.cos(SPLIT_ANG), 0)) * 6
    p1 = Vector((side * BR_X, Y_SPLIT + BR_LEN, 0))
    t1 = Vector((0, 1, 0)) * 6
    plan = D.plan_along(hermite(p0, t0, p1, t1))        # 첫 도미노는 분기점에 딱 붙임
    # 계단 위 자리: 바닥 마지막 도미노 바로 다음 칸부터
    y_st = plan[-1][0].y + TREAD
    for i in range(N_UP):
        plan.append((Vector((p1.x, y_st + TREAD * i, RISE * (i + 1))), 0.0, 1.0, 1.0))
    doms = D.build_plan(plan, color_fn=colors, prefix=name)
    # 계단
    for i in range(N_UP):
        h = RISE * (i + 1)
        D.box(f'{name}_Step{i}', (p1.x, y_st + TREAD * i, h / 2), (0.9, TREAD, h), STAIR_MAT)
    # 받침대 (계단 맨 위와 같은 높이) + 구슬
    top_h = RISE * N_UP
    last_y = y_st + TREAD * (N_UP - 1)
    plat_len = 0.9
    D.box(f'{name}_Platform', (p1.x, last_y + TREAD / 2 + plat_len / 2, top_h / 2),
          (0.9, plat_len, top_h), STAIR_MAT)
    ball_y = last_y + 0.62
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R_BALL, segments=48, ring_count=24,
                                         location=(p1.x, ball_y, top_h + R_BALL + 0.002))
    ball = bpy.context.object
    ball.name = f'{name}_Ball'
    bpy.ops.object.shade_smooth()
    ball.data.materials.append(D.glass_marble_mat(BALL_RGB[side]))
    D.add_rigid(ball, 'ACTIVE', mass=0.15, friction=0.4, bounce=0.1, shape='SPHERE')
    # 경사로: 받침대 끝에서 바닥까지, 양옆 턱
    y0 = last_y + TREAD / 2 + plat_len
    ang = math.atan2(top_h, RAMP_L)
    L = math.hypot(top_h, RAMP_L)
    ramp_c = Vector((p1.x, y0 + RAMP_L / 2, top_h / 2))
    for dx, w, hgt, dz in [(0, 0.8, 0.08, -0.04), (-0.42, 0.06, 0.2, 0.06), (0.42, 0.06, 0.2, 0.06)]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=ramp_c + Vector((dx, 0, dz)))
        r = bpy.context.object
        r.name = f'{name}_Ramp'
        r.scale = (w, L, hgt)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        r.rotation_euler = (-ang, 0, 0)
        r.data.materials.append(BRASS if dx else TREAD_MAT)
        D.add_rigid(r, 'PASSIVE', friction=0.5)
    return doms, ball


BALL_RGB = {-1: (0.95, 0.45, 0.6),      # 분홍 송편
            1: (0.55, 0.85, 0.35)}      # 연두(쑥) 송편
left, ball_l = branch(-1, lambda u: D.rainbow(0.0 + 0.17 * u), 'BrL')     # 빨강 → 노랑
right, ball_r = branch(1, lambda u: D.rainbow(0.45 + 0.2 * u), 'BrR')     # 청록 → 파랑

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
D.camera(loc=(0.0, -9.0, 9.5), target=(0.0, 3.5, 0.5), lens=24, dof_fstop=None)
D.render_setup(scene, preview=True)

allobjs = trunk + left + right
print(f'도미노 {len(allobjs)}개 (왼쪽 {len(left)}, 오른쪽 {len(right)})')

# 도미노 + 구슬 동시성 확인
ramp_end_y = None
arrive = {}
first = {}
for f in range(1, FRAMES + 1):
    scene.frame_set(f)
    for o in (left[0], right[0], left[-1], right[-1]):
        if o.name not in first and D.tilt(o)[0] > 10:
            first[o.name] = f
    for b in (ball_l, ball_r):
        if b.name not in arrive and b.matrix_world.translation.z < R_BALL + 0.02 and \
                b.matrix_world.translation.y > BR_LEN + 5:
            arrive[b.name] = f
print('  갈래 첫 도미노 쓰러진 프레임:', first.get(left[0].name), first.get(right[0].name))
print('  갈래 끝 도미노 쓰러진 프레임:', first.get(left[-1].name), first.get(right[-1].name))
print('  구슬이 바닥에 내려온 프레임:', arrive)
scene.frame_set(FRAMES)
for b in (ball_l, ball_r):
    p = b.matrix_world.translation
    print(f'  {b.name} 끝 위치 ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})')
standing = [o.name for o in allobjs if D.tilt(o)[0] < 45]
print(f'  결과: 서 있음 {len(standing)}', standing[:8])

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene06_f{f:03d}.png'))
