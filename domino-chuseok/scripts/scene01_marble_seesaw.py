# =========================================================
#  장면 1 (0–10초): 송편 구슬 → 나선 레일 → 깔때기 → 시소 → 첫 도미노
#  실행: blender -b -P scripts/scene01_marble_seesaw.py              (물리 검증)
#        blender -b -P scripts/scene01_marble_seesaw.py -- render 1 90 (스틸 렌더)
#        blender -b -P scripts/scene01_marble_seesaw.py -- track        (구슬 위치 추적)
# =========================================================
import bpy, bmesh, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAMES = 450
scene = D.reset_scene(frames=FRAMES, time_scale=1.6)
D.wood_floor()

R_BALL = 0.22          # 구슬 반지름 (첫 도미노 0.55배에 맞춘 크기)
R_RAIL = 0.035         # 레일 파이프 반지름
RAIL_MAT = D.simple_mat('Brass', (0.85, 0.62, 0.3), rough=0.25, metal=1.0)
WOOD_MAT = D.simple_mat('LacquerWood', (0.35, 0.08, 0.05), rough=0.3, coat=0.6)   # 옻칠한 붉은 나무


# ---------- 파이프(레일) 만들기 ----------
def tube(points, radius, name, mat, physics=True):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(points) - 1)
    for p, v in zip(sp.points, points):
        p.co = (v.x, v.y, v.z, 1)
    obj = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    if physics:
        D.add_rigid(obj, 'PASSIVE', friction=0.3, bounce=0.1, shape='MESH')
    return obj


def frame_at(pts, i):
    """경로 i번째 점의 (접선 T, 옆 N, 위 U)."""
    a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
    T = (b - a).normalized()
    N = T.cross(Vector((0, 0, 1))).normalized()     # 진행 방향 오른쪽
    U = N.cross(T).normalized()
    return T, N, U


def rails_along(center, name):
    """구슬 중심 경로를 따라 받침 레일 2개 + 옆 가드 레일 2개."""
    d = (R_BALL + R_RAIL)
    lo = d / math.sqrt(2)
    offsets = {'L': (-lo, -lo), 'R': (lo, -lo), 'GL': (-d * 1.02, 0.12), 'GR': (d * 1.02, 0.12)}
    out = []
    for key, (side, up) in offsets.items():
        pts = []
        for i, c in enumerate(center):
            T, N, U = frame_at(center, i)
            pts.append(c + N * side + U * up)
        out.append(tube(pts, R_RAIL, f'{name}_{key}', RAIL_MAT))
    return out


# ---------- 1) 나선 레일 ----------
HELIX_R, TURNS, Z_TOP, DROP_PER_TURN = 1.3, 2.25, 6.2, 1.05
helix = []
steps = 360
for i in range(steps + 1):
    th = TURNS * 2 * math.pi * i / steps
    helix.append(Vector((HELIX_R * math.cos(th), HELIX_R * math.sin(th),
                         Z_TOP - DROP_PER_TURN * th / (2 * math.pi))))
# 끝에서 접선 방향으로 곧게 뻗는 출구
T_end = (helix[-1] - helix[-2]).normalized()
for k in range(1, 16):
    helix.append(helix[-1] + T_end * 0.07)
rails_along(helix, 'Helix')

# 가운데 기둥 + 받침대 (장식, 물리 없음)
bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=Z_TOP + 0.6, location=(0, 0, (Z_TOP + 0.6) / 2))
pole = bpy.context.object
pole.name = 'HelixPole'
pole.data.materials.append(WOOD_MAT)
for i in range(0, steps, 30):     # 기둥에서 레일로 가는 가로대
    c = helix[i]
    T, N, U = frame_at(helix, i)
    inner = c - N * 0  # noqa
    a = Vector((0, 0, c.z - 0.2))
    b = Vector((c.x, c.y, 0)) * ((HELIX_R - 0.35) / HELIX_R) + Vector((0, 0, c.z - 0.2))
    tube([a, b], 0.025, f'Spoke_{i}', RAIL_MAT, physics=False)

# ---------- 구슬 ----------
T0, N0, U0 = frame_at(helix, 0)
bpy.ops.mesh.primitive_uv_sphere_add(radius=R_BALL, segments=48, ring_count=24,
                                     location=helix[0] + T0 * 0.15)
ball = bpy.context.object
ball.name = 'Songpyeon_Pink'
bpy.ops.object.shade_smooth()
ball.data.materials.append(D.glass_marble_mat((0.95, 0.45, 0.6)))
D.add_rigid(ball, 'ACTIVE', mass=0.12, friction=0.35, bounce=0.15, shape='SPHERE')


# ---------- 2) 깔때기 ----------
exit_c = helix[-1]
FUN_R, HOLE_R, LIP = 1.1, 0.3, 0.22
WELL_K = 0.55                                     # 중력 우물 곡선 z = -K(1/r - 1/R)
FUN_DEPTH = WELL_K * (1 / HOLE_R - 1 / FUN_R)
side = T_end.cross(Vector((0, 0, 1))).normalized()          # 출구 진행 방향 오른쪽
# 구슬이 가장자리를 따라 접선으로 들어가도록 중심을 옆으로
fun_c = Vector((exit_c.x, exit_c.y, 0)) + side * (FUN_R - R_BALL - 0.12)
RIM_Z = exit_c.z - R_BALL - LIP - 0.08
PIPE_END_Z = 0.8
fun_c.z = RIM_Z

def build_funnel():
    bm = bmesh.new()
    seg, rings = 72, 28
    prof = []
    for j in range(rings + 1):      # 가장자리 → 구멍 (동전 소용돌이 모금함 곡선)
        u = j / rings
        r = FUN_R + (HOLE_R - FUN_R) * u
        z = -WELL_K * (1 / r - 1 / FUN_R)
        prof.append((r, z))
    prof.insert(0, (FUN_R, LIP))                 # 가장자리 벽
    prof.append((HOLE_R, -(RIM_Z - PIPE_END_Z))) # 아래로 뻗은 관: 구슬이 곧게 떨어지게
    verts = []
    for r, z in prof:
        ring = [bm.verts.new((fun_c.x + r * math.cos(2 * math.pi * k / seg),
                              fun_c.y + r * math.sin(2 * math.pi * k / seg), fun_c.z + z))
                for k in range(seg)]
        verts.append(ring)
    for a, b in zip(verts, verts[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    me = bpy.data.meshes.new('Funnel')
    bm.to_mesh(me)
    obj = bpy.data.objects.new('Funnel', me)
    scene.collection.objects.link(obj)
    mod = obj.modifiers.new('Solid', 'SOLIDIFY')
    mod.thickness = 0.03
    mod.offset = 0.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier='Solid')
    bpy.ops.object.shade_smooth()
    m = D.simple_mat('FunnelGlass', (0.95, 0.85, 0.6), rough=0.15, metal=0.0, coat=1.0)
    m.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value = 0.6
    obj.data.materials.append(m)
    D.add_rigid(obj, 'PASSIVE', friction=0.25, bounce=0.1, shape='MESH')
    # 다리 3개
    base = math.atan2(fun_c.y, fun_c.x)            # 시소 방향과 겹치지 않게 90/210/330도
    for k in range(3):
        a = base + math.radians(90 + 120 * k)
        top = fun_c + Vector((FUN_R * math.cos(a), FUN_R * math.sin(a), 0))
        tube([Vector((top.x, top.y, 0)), top], 0.04, f'FunnelLeg_{k}', RAIL_MAT, physics=False)
    return obj

build_funnel()

# ---------- 3) 시소 ----------
hole = Vector((fun_c.x, fun_c.y, 0))
away = Vector((hole.x, hole.y, 0)).normalized()          # 나선 반대쪽으로 향함
PLANK_L, PIVOT_H = 3.0, 0.32
pivot = hole - away * 0.55
pivot.z = PIVOT_H
yaw = math.atan2(away.y, away.x)
tiltang = math.asin((PIVOT_H - 0.05) / (PLANK_L / 2))

# 판자 + 양옆 턱(홈 모양): 구슬이 판자 길이 방향으로만 굴러가게
PLANK_W, LIP_H = 0.62, 0.12
bm = bmesh.new()
from mathutils import Matrix
for (sx, sy, sz, oy, oz) in [(PLANK_L, PLANK_W, 0.08, 0, 0),
                             (PLANK_L, 0.05, LIP_H, (PLANK_W - 0.05) / 2, LIP_H / 2 + 0.02),
                             (PLANK_L, 0.05, LIP_H, -(PLANK_W - 0.05) / 2, LIP_H / 2 + 0.02)]:
    bmesh.ops.create_cube(bm, size=1.0,
                          matrix=Matrix.Translation((0, oy, oz)) @ Matrix.Diagonal((sx, sy, sz, 1)))
me = bpy.data.meshes.new('Seesaw')
bm.to_mesh(me)
plank = bpy.data.objects.new('Seesaw', me)
scene.collection.objects.link(plank)
plank.location = pivot
bev = plank.modifiers.new('Bevel', 'BEVEL'); bev.width = 0.012; bev.segments = 2
plank.rotation_euler = (0, -tiltang, yaw)       # 공 쪽(+away) 끝이 위로
plank.data.materials.append(WOOD_MAT)
D.add_rigid(plank, 'ACTIVE', mass=0.25, friction=0.5, bounce=0.05, shape='MESH')
plank.rigid_body.angular_damping = 0.3

# 받침 (삼각 기둥)
bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=0.26, depth=0.5,
                                    location=(pivot.x, pivot.y, 0.13))
fulcrum = bpy.context.object
fulcrum.name = 'Fulcrum'
fulcrum.rotation_euler = (math.radians(90), 0, yaw + math.radians(90))
fulcrum.rotation_euler.rotate_axis('Z', math.radians(30))
fulcrum.data.materials.append(RAIL_MAT)
D.add_rigid(fulcrum, 'PASSIVE', shape='MESH')

bpy.ops.object.empty_add(location=pivot)
hinge = bpy.context.object
hinge.name = 'SeesawHinge'
hinge.rotation_euler = (math.radians(90), 0, yaw)       # 경첩 축(Z) = 판자 가로 방향
bpy.ops.rigidbody.constraint_add(type='HINGE')
hinge.rigid_body_constraint.object1 = fulcrum
hinge.rigid_body_constraint.object2 = plank

# ---------- 4) 첫 도미노 줄 ----------
start = pivot + away * (PLANK_L / 2 + 0.75)
line_pts = [Vector((start.x, start.y, 0)) + away * (0.05 * i) for i in range(160)]
line = D.dominoes_along(line_pts, scale_fn=lambda u: 0.55 + 0.25 * u,
                        color_fn=lambda u: D.rainbow(u * 0.25), prefix='L1')

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
mid = (Vector((0, 0, 2.5)) + pivot) / 2
D.camera(loc=mid + Vector((-away.y, away.x, 0)) * 9 + Vector((0, 0, 2.5)) - away * 1.5,
         target=mid, lens=26, dof_fstop=None)
D.render_setup(scene, preview=True)

print(f'도미노 {len(line)}개, 시소 방향 {math.degrees(yaw):.0f}도')

if 'track' in ARGS:
    for f in range(1, FRAMES + 1):
        scene.frame_set(f)
        if f % 10 == 0:
            p = ball.matrix_world.translation
            pa = math.degrees(plank.matrix_world.to_euler().y)
            print(f'  f{f:4d} 구슬 ({p.x:5.2f},{p.y:5.2f},{p.z:5.2f})  시소 {pa:5.1f}도')
else:
    D.verify(scene, line, every=30)

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene01_f{f:03d}.png'))
