# =========================================================
#  질감·디테일 테스트: 구슬 → 점점 커지는 무지개 S자 줄
#  실행: blender -b -P scripts/look_test.py            (물리 검증)
#        blender -b -P scripts/look_test.py -- render  (확인용 스틸 렌더)
# =========================================================
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

scene = D.reset_scene(frames=150, time_scale=2.5)
D.wood_floor()

# S자 경로: y 방향으로 달리며 좌우로 흔들림
def s_curve(t):
    return (1.6 * math.sin(t * math.pi * 1.5), t * 12.0)

pts = D.path_points(s_curve, 0.0, 1.0)
line = D.dominoes_along(pts, scale_fn=lambda u: 0.55 + 0.9 * u, prefix='S')

# 구슬 + 경사로 (첫 도미노 뒤쪽에서 굴러옴)
first = line[0]
fwd = first.matrix_world.to_3x3() @ Vector((0, 1, 0))
ANG, L, R = math.radians(20), 3.0, 0.22
down = Vector((fwd.x * math.cos(ANG), fwd.y * math.cos(ANG), -math.sin(ANG)))
normal = Vector((fwd.x * math.sin(ANG), fwd.y * math.sin(ANG), math.cos(ANG)))
bottom = Vector((first.location.x, first.location.y, 0)) - fwd * 0.9
top = bottom - down * L
bpy.ops.mesh.primitive_cube_add(size=1, location=(top + bottom) / 2 - normal * 0.05)
ramp = bpy.context.object
ramp.name = 'Ramp'
ramp.scale = (0.8, L, 0.1)
ramp.rotation_euler = (-ANG, 0, math.atan2(-fwd.x, fwd.y))
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
ramp.data.materials.append(D.simple_mat('Ramp', (0.85, 0.82, 0.76), rough=0.35, coat=0.3))
D.add_rigid(ramp, 'PASSIVE', friction=0.6)

bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=48, ring_count=24,
                                     location=top + down * 0.3 + normal * (R + 0.01))
ball = bpy.context.object
ball.name = 'Songpyeon_Pink'
bpy.ops.object.shade_smooth()
ball.data.materials.append(D.glass_marble_mat((0.95, 0.45, 0.6)))
D.add_rigid(ball, 'ACTIVE', mass=0.3 * 0.55 ** 3 * 1.5, friction=0.4, bounce=0.2, shape='SPHERE')

D.night_lighting(scene)
D.camera(loc=(4.2, -5.5, 2.2), target=(0.3, 2.5, 0.4), lens=28, dof_fstop=3.2)
D.render_setup(scene, preview=True)

print(f'도미노 {len(line)}개')
D.verify(scene, line, every=30)

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1, 120]:
        D.render_still(scene, f, os.path.join(out, f'look_test_f{f:03d}.png'))
