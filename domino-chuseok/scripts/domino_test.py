# =========================================================
#  도미노 물리 테스트 (Blender 4.2 이상)
#  구슬이 경사로를 굴러 내려와 도미노 10개를 쓰러뜨립니다.
#  사용법: Scripting 탭 → New → 이 코드 붙여넣기 → Run Script
# =========================================================
import bpy, math, os
from mathutils import Vector

# ---------- 장면 초기화 ----------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, 180      # 30fps x 6초
scene.render.fps = 30

if scene.rigidbody_world is None:
    bpy.ops.rigidbody.world_add()
rbw = scene.rigidbody_world
rbw.substeps_per_frame = 20        # 물리 계산 정밀도 (높을수록 정확, 느림)
rbw.solver_iterations = 30
rbw.point_cache.frame_start, rbw.point_cache.frame_end = 1, 180

# ---------- 재질 ----------
def make_mat(name, rgb, rough=0.4, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m

def add_rigid(obj, kind='ACTIVE', mass=1.0, friction=0.5, bounce=0.1, shape='BOX'):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = kind
    rb.mass = mass
    rb.friction = friction
    rb.restitution = bounce
    rb.collision_shape = shape
    rb.use_margin = True
    rb.collision_margin = 0.001

# ---------- 바닥 ----------
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
floor = bpy.context.object
floor.data.materials.append(make_mat('Floor', (0.12, 0.09, 0.07), rough=0.6))
add_rigid(floor, 'PASSIVE', friction=0.8, shape='MESH')

# ---------- 도미노 10개 ----------
H, Wd, T, GAP = 1.0, 0.5, 0.15, 0.6        # 높이, 폭, 두께, 간격
for i in range(10):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, i * GAP, H / 2))
    d = bpy.context.object
    d.name = f'Domino_{i:02d}'
    d.scale = (Wd, T, H)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    hue_rgb = [(0.95, 0.25, 0.25), (0.98, 0.55, 0.2), (0.98, 0.85, 0.25), (0.45, 0.85, 0.3),
               (0.25, 0.75, 0.6), (0.25, 0.65, 0.95), (0.35, 0.4, 0.95), (0.6, 0.35, 0.9),
               (0.9, 0.35, 0.75), (0.95, 0.3, 0.45)][i]
    d.data.materials.append(make_mat(f'Dom{i}', hue_rgb, rough=0.25))
    add_rigid(d, 'ACTIVE', mass=0.2, friction=0.8, bounce=0.05)

# ---------- 경사로 ----------
ANG = math.radians(20)
L = 4.0
bottom = Vector((0, -1.2, 0))
down_dir = Vector((0, math.cos(ANG), -math.sin(ANG)))       # 경사 아래 방향
normal = Vector((0, math.sin(ANG), math.cos(ANG)))          # 경사면 위쪽 법선
top = bottom - down_dir * L
center = (top + bottom) / 2 - normal * 0.05
bpy.ops.mesh.primitive_cube_add(size=1, location=center)
ramp = bpy.context.object
ramp.name = 'Ramp'
ramp.scale = (1.0, L, 0.1)
ramp.rotation_euler = (-ANG, 0, 0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
ramp.data.materials.append(make_mat('Ramp', (0.9, 0.88, 0.84), rough=0.5))
add_rigid(ramp, 'PASSIVE', friction=0.6, shape='BOX')

# ---------- 구슬 ----------
R = 0.3
start = top + down_dir * 0.4 + normal * (R + 0.01)
bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=48, ring_count=24, location=start)
ball = bpy.context.object
ball.name = 'Marble'
bpy.ops.object.shade_smooth()
ball.data.materials.append(make_mat('Marble', (0.85, 0.08, 0.12), rough=0.05))
add_rigid(ball, 'ACTIVE', mass=0.3, friction=0.4, bounce=0.2, shape='SPHERE')

# ---------- 조명 ----------
bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
sun = bpy.context.object
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(45), math.radians(-20), math.radians(30))
bpy.ops.object.light_add(type='AREA', location=(-3, -2, 5))
area = bpy.context.object
area.data.energy = 400
area.data.size = 4

world = scene.world or bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.02, 0.025, 1)

# ---------- 카메라 ----------
bpy.ops.object.empty_add(location=(0, 1.2, 0.4))
target = bpy.context.object
target.name = 'CamTarget'
bpy.ops.object.camera_add(location=(5.0, -5.5, 3.2))
cam = bpy.context.object
cam.data.lens = 32
con = cam.constraints.new('TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'
scene.camera = cam

# ---------- 렌더 설정 (Eevee, 세로 1080x1920, MP4) ----------
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        pass
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
try:
    scene.render.image_settings.media_type = 'VIDEO'   # Blender 5.x
except (AttributeError, TypeError):
    pass
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'

desk = os.path.join(os.path.expanduser('~'), 'Desktop')
if not os.path.isdir(desk):
    desk = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
if not os.path.isdir(desk):
    desk = os.path.expanduser('~')
scene.render.filepath = os.path.join(desk, 'domino_test_')

scene.frame_set(1)
print('도미노 테스트 장면 준비 완료. 3D 화면에서 스페이스바를 눌러 재생하세요.')
