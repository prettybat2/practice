# =========================================================
#  장면 5 (28–36초): 위에서 본 나선 필드 — 쓰러지며 보름달이 드러남
#  도미노 앞·옆은 밤하늘색, 뒷면(쓰러지면 위로 오는 면)은 보름달 색(분화구 무늬)
#  실행: blender -b -P scripts/scene05_moon_spiral.py              (물리 검증)
#        blender -b -P scripts/scene05_moon_spiral.py -- render 1 200
# =========================================================
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector, noise

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAMES = 450
scene = D.reset_scene(frames=FRAMES, time_scale=2.5)
D.wood_floor()

R_OUT, R_IN = 4.4, 1.3
PITCH = 0.62                         # 나선 한 바퀴마다 줄어드는 반지름 (도미노 폭 0.5 + 옆 바퀴와 충분한 틈)
B = PITCH / (2 * math.pi)


def spiral_pt(th):
    r = R_OUT - B * th
    return Vector((r * math.cos(th), r * math.sin(th), 0))


th_end = (R_OUT - R_IN) / B
n = int(th_end / 0.01)
spiral = [spiral_pt(th_end * i / n) for i in range(n + 1)]
t0 = (spiral[1] - spiral[0]).normalized()
lead_in = D.straight(spiral[0] - t0 * 4.0, spiral[0], n=100)
path = D.polyline(lead_in, spiral)


MOON_BASE = Vector((1.0, 0.72, 0.22))                  # 추석 보름달 황금빛
CRATERS = [((-1.6, 1.4), 1.1, 0.35), ((1.2, 2.2), 0.8, 0.3), ((2.1, -0.8), 1.0, 0.3),
           ((-0.6, -2.4), 1.2, 0.35), ((-2.8, -0.9), 0.7, 0.28), ((0.5, 0.6), 0.6, 0.2)]


def moon_rgb(p):
    """보름달 색: 황금빛 바탕 + 분화구(둥근 어두운 얼룩) + 잔무늬 + 가장자리 살짝 어둡게."""
    shade = 1.0
    for (cx, cy), rad, depth in CRATERS:
        d = math.hypot(p.x - cx, p.y - cy) / rad
        if d < 1.0:
            shade -= depth * (1 - d * d)
    shade -= 0.12 * max(noise.noise(Vector((p.x * 1.4, p.y * 1.4, 7.7))), 0)
    shade -= 0.15 * (p.length / R_OUT) ** 3
    return tuple(max(0.0, min(1.0, v * shade)) for v in MOON_BASE)


def night_rgb(u):
    """앞·옆면: 남색 → 보라 → 자주 (밤하늘)."""
    import colorsys
    return colorsys.hsv_to_rgb(0.62 + 0.2 * u, 0.75, 0.55)


plan = D.plan_along(path, scale_fn=lambda u: 1.0)
dominoes = []
for i, (p, yaw, sc, u) in enumerate(plan):
    in_field = p.length <= R_OUT + 0.05
    dominoes.append(D.make_domino(p, yaw, sc, night_rgb(u), f'M_{i:03d}',
                                  face_rgb=moon_rgb(p) if in_field else None))
D.lean(dominoes[0])

# ---------- 밤하늘 원판 (나선 아래, 장식) ----------
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=R_OUT + 0.45, fill_type='NGON', location=(0, 0, 0.002))
sky = bpy.context.object
sky.name = 'NightDisc'
sky.data.materials.append(D.simple_mat('NightDisc', (0.015, 0.02, 0.06), rough=0.6))

# 가운데 달 원판: 처음부터 빛나고, 나선이 넘어가며 바깥으로 달이 채워짐
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=R_IN - 0.15, depth=0.06, location=(0, 0, 0.03))
core = bpy.context.object
core.name = 'MoonCore'
cm = D.simple_mat('MoonCore', tuple(MOON_BASE), rough=0.35, coat=0.3)
bsdf = cm.node_tree.nodes['Principled BSDF']
bsdf.inputs['Emission Color'].default_value = (*MOON_BASE, 1)
bsdf.inputs['Emission Strength'].default_value = 0.6
core.data.materials.append(cm)

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
D.camera(loc=(0.0, -2.5, 17.0), target=(0.0, 0.0, 0.0), lens=30, dof_fstop=None)
D.render_setup(scene, preview=True)
scene.view_settings.exposure = -1.2        # 위에서 내려다보면 조명이 세서 달 색이 날아감

print(f'도미노 {len(dominoes)}개, 나선 {th_end / (2 * math.pi):.1f}바퀴')
D.verify(scene, dominoes, every=30)

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene05_f{f:03d}.png'))
