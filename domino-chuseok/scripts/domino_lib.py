# =========================================================
#  도미노 공용 라이브러리 (Blender 5.0)
#  모든 장면 스크립트가 import 해서 쓰는 도구 모음입니다.
#  - 디테일 도미노(모서리 둥글림, 플라스틱 재질)
#  - 경로를 따라 도미노 줄 깔기 (크기 점점 커지기 지원)
#  - 나무 마루 바닥, 밤 조명, 카메라, 렌더 설정
#  - 물리 검증(각 도미노 기울기 출력)
# =========================================================
import bpy, math, os, colorsys
from mathutils import Vector, Matrix

# ---------- 기본 치수 (브리프 4장에서 검증된 값) ----------
DOM_H, DOM_W, DOM_T = 1.0, 0.5, 0.15
DOM_MASS, DOM_FRICTION = 0.2, 0.8
GAP_RATIO = 0.6            # 간격 = 높이 x 0.6


# ---------- 장면 ----------
def reset_scene(frames=180, fps=30, time_scale=1.0):
    _mat_cache.clear()
    _dom_mesh_cache.clear()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
        for item in list(block):
            if item.users == 0:
                block.remove(item)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.fps = fps
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.substeps_per_frame = 20
    rbw.solver_iterations = 30
    rbw.time_scale = time_scale
    rbw.point_cache.frame_start, rbw.point_cache.frame_end = 1, frames
    return scene


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
    return rb


# ---------- 재질 ----------
_mat_cache = {}

def plastic_mat(rgb, name=None):
    """광택 있는 도미노 플라스틱. 같은 색은 재사용."""
    key = ('plastic',) + tuple(round(c, 3) for c in rgb)
    if key in _mat_cache:
        return _mat_cache[key]
    m = bpy.data.materials.new(name or f'Plastic_{len(_mat_cache)}')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = 0.28
    b.inputs['Coat Weight'].default_value = 0.35
    b.inputs['Coat Roughness'].default_value = 0.08
    # 미세한 표면 요철 (사출 플라스틱 느낌)
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 180
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.03
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    _mat_cache[key] = m
    return m


def simple_mat(name, rgb, rough=0.4, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    return m


def glass_marble_mat(rgb, name='Marble'):
    """송편 구슬: 반투명 유리 + 안쪽 색."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = 0.04
    b.inputs['Subsurface Weight'].default_value = 0.35
    b.inputs['Subsurface Radius'].default_value = (0.3, 0.2, 0.2)
    b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.02
    return m


def wood_mat():
    """한옥 마루 느낌의 나무 바닥 (절차적 나뭇결 + 판자 이음새)."""
    m = bpy.data.materials.new('WoodFloor')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    coord = nt.nodes.new('ShaderNodeTexCoord')
    mapping = nt.nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (1.0, 0.06, 1.0)   # Y 방향으로 길게 늘인 결
    nt.links.new(coord.outputs['Object'], mapping.inputs['Vector'])
    grain = nt.nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value = 3.0
    grain.inputs['Detail'].default_value = 8.0
    grain.inputs['Distortion'].default_value = 0.6
    nt.links.new(mapping.outputs['Vector'], grain.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.11, 0.05, 0.022, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.25, 0.13, 0.055, 1)
    nt.links.new(grain.outputs['Fac'], ramp.inputs['Fac'])
    # 판자 이음새: 벽돌 텍스처로 가는 어두운 줄
    brick = nt.nodes.new('ShaderNodeTexBrick')
    brick.inputs['Scale'].default_value = 0.35
    brick.inputs['Mortar Size'].default_value = 0.006
    brick.inputs['Brick Width'].default_value = 6.0
    brick.inputs['Row Height'].default_value = 0.5
    brick.inputs['Color1'].default_value = (1, 1, 1, 1)
    brick.inputs['Color2'].default_value = (0.85, 0.85, 0.85, 1)
    brick.inputs['Mortar'].default_value = (0.25, 0.25, 0.25, 1)
    rot = nt.nodes.new('ShaderNodeMapping')
    rot.inputs['Rotation'].default_value = (0, 0, math.radians(90))
    nt.links.new(coord.outputs['Object'], rot.inputs['Vector'])
    nt.links.new(rot.outputs['Vector'], brick.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    nt.links.new(ramp.outputs['Color'], mix.inputs['A'])
    nt.links.new(brick.outputs['Color'], mix.inputs['B'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.5
    b.inputs['Coat Weight'].default_value = 0.15
    return m


# ---------- 무지개 색 ----------
def rainbow(t, sat=0.88, val=0.92):
    """t=0~1 → 빨강에서 보라까지."""
    return colorsys.hsv_to_rgb((t * 0.83) % 1.0, sat, val)


# ---------- 도미노 ----------
_dom_mesh_cache = {}

def _domino_mesh(scale, two_tone=False):
    """모서리를 둥글린 도미노 메시 (크기별로 공유해서 가볍게).
    two_tone=True면 뒷면(-Y, 앞으로 넘어지면 위를 보는 면)에 재질 슬롯 1을 준다."""
    key = (round(scale, 3), two_tone)
    if key in _dom_mesh_cache:
        return _dom_mesh_cache[key]
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    tmp = bpy.context.object
    tmp.scale = (DOM_W * scale, DOM_T * scale, DOM_H * scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = tmp.modifiers.new('Bevel', 'BEVEL')
    mod.width = 0.018 * scale
    mod.segments = 3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    mesh = tmp.data
    mesh.name = f'DominoMesh_{key[0]}_{int(two_tone)}'
    if two_tone:
        mesh.materials.append(None)
        mesh.materials.append(None)
        for poly in mesh.polygons:
            poly.material_index = 1 if poly.normal.y < -0.5 else 0
    bpy.data.objects.remove(tmp, do_unlink=True)
    _dom_mesh_cache[key] = mesh
    return mesh


FACE_EMISSION = 0.0      # 뒷면 그림 발광 세기 (장면별로 조정, 그림을 선명하게)


def face_mat():
    """오브젝트마다 다른 색을 쓰는 뒷면 재질 (obj.color 사용) — 그림 공개용."""
    if 'face' in _mat_cache:
        return _mat_cache['face']
    m = bpy.data.materials.new('FaceByObjectColor')
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    info = nt.nodes.new('ShaderNodeObjectInfo')
    nt.links.new(info.outputs['Color'], b.inputs['Base Color'])
    nt.links.new(info.outputs['Color'], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = FACE_EMISSION
    b.inputs['Roughness'].default_value = 0.35
    b.inputs['Coat Weight'].default_value = 0.2
    _mat_cache['face'] = m
    return m


def add_rigid_batch(objs, mass_fn, friction=DOM_FRICTION, bounce=0.05, shape='BOX'):
    """여러 오브젝트에 강체를 한 번에 붙인다 (하나씩 붙이면 개수²로 느려짐 — 수천 개일 때 필수)."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.rigidbody.objects_add(type='ACTIVE')
    for o in objs:
        rb = o.rigid_body
        rb.mass = mass_fn(o)
        rb.friction = friction
        rb.restitution = bounce
        rb.collision_shape = shape
        rb.use_margin = True
        rb.collision_margin = 0.001
    bpy.ops.object.select_all(action='DESELECT')


def make_domino(loc, yaw=0.0, scale=1.0, rgb=(0.9, 0.3, 0.3), name='Domino',
                mass=None, collection=None, face_rgb=None, rigid=True):
    """loc = 바닥 중심 좌표 (z는 바닥 높이), yaw = 쓰러지는 방향 각(라디안, +Y 기준).
    face_rgb를 주면 뒷면만 그 색 (쓰러지면 드러나는 그림 픽셀)."""
    mesh = _domino_mesh(scale, two_tone=face_rgb is not None)
    obj = bpy.data.objects.new(name, mesh)
    (collection or bpy.context.scene.collection).objects.link(obj)
    obj.location = Vector(loc) + Vector((0, 0, DOM_H * scale / 2))
    obj.rotation_euler = (0, 0, yaw)
    if not mesh.materials:
        mesh.materials.append(plastic_mat(rgb))
    # 메시를 공유하므로 색은 오브젝트 단위 재질로
    obj.material_slots[0].link = 'OBJECT'
    obj.material_slots[0].material = plastic_mat(rgb)
    if face_rgb is not None:
        obj.material_slots[1].link = 'OBJECT'
        obj.material_slots[1].material = face_mat()
        obj.color = (*face_rgb, 1)
    if rigid:
        add_rigid(obj, 'ACTIVE', mass=(mass or DOM_MASS) * scale ** 3,
                  friction=DOM_FRICTION, bounce=0.05, shape='BOX')
    obj['domino'] = True
    return obj


def path_points(fn, t0, t1, samples=2000):
    """매개변수 곡선 fn(t)->(x,y)를 촘촘히 샘플링."""
    return [Vector((*fn(t0 + (t1 - t0) * i / samples), 0)) for i in range(samples + 1)]


def plan_along(points, scale_fn=lambda u: 1.0, z=0.0, start_offset=0.0, align_end=False):
    """점 목록을 따라 도미노 자리 계획만 세운다 → [(위치, yaw, 크기, u)].
    간격은 각 도미노 크기에 비례. align_end=True면 마지막 도미노가 정확히 끝점에 오도록 민다."""
    seg = [0.0]
    for a, b in zip(points, points[1:]):
        seg.append(seg[-1] + (b - a).length)
    total = seg[-1]

    def at(s):
        i = 0
        lo, hi = 0, len(seg) - 2
        while lo < hi:                      # 이분 탐색
            mid = (lo + hi + 1) // 2
            if seg[mid] <= s:
                lo = mid
            else:
                hi = mid - 1
        i = lo
        a, b = points[i], points[i + 1]
        f = (s - seg[i]) / max(seg[i + 1] - seg[i], 1e-9)
        d = (b - a).normalized()
        return a.lerp(b, f), math.atan2(-d.x, d.y)

    ss, s = [], start_offset
    while s <= total + 1e-6:
        ss.append(s)
        s += DOM_H * scale_fn(min(s / total, 1.0)) * GAP_RATIO
    if align_end and ss:
        shift = total - ss[-1]
        ss = [v + shift for v in ss]
    out = []
    for s in ss:
        p, yaw = at(min(s, total))
        u = min(s / total, 1.0)
        out.append((Vector((p.x, p.y, z)), yaw, scale_fn(u), u))
    return out


def build_plan(plan, color_fn=rainbow, prefix='Dom'):
    """plan = [(위치, yaw, 크기, u)] → 도미노 생성. 색은 전체 순서 기준 0~1."""
    n = max(len(plan) - 1, 1)
    return [make_domino(p, yaw, sc, color_fn(i / n), f'{prefix}_{i:03d}')
            for i, (p, yaw, sc, u) in enumerate(plan)]


def dominoes_along(points, scale_fn=lambda u: 1.0, color_fn=rainbow, z=0.0,
                   prefix='Line', start_offset=0.0, align_end=False):
    plan = plan_along(points, scale_fn, z, start_offset, align_end)
    return [make_domino(p, yaw, sc, color_fn(u), f'{prefix}_{i:03d}')
            for i, (p, yaw, sc, u) in enumerate(plan)]


def polyline(*pieces, step=0.02):
    """여러 조각(점 목록)을 이어 붙이고 촘촘히 다시 샘플링."""
    pts = []
    for piece in pieces:
        for p in piece:
            if not pts or (p - pts[-1]).length > 1e-6:
                pts.append(p)
    return pts


def arc(center, radius, a0, a1, n=200):
    return [Vector((center[0] + radius * math.cos(a0 + (a1 - a0) * i / n),
                    center[1] + radius * math.sin(a0 + (a1 - a0) * i / n), 0)) for i in range(n + 1)]


def straight(a, b, n=100):
    a, b = Vector((*a, 0)) if len(a) == 2 else Vector(a), Vector((*b, 0)) if len(b) == 2 else Vector(b)
    return [a.lerp(b, i / n) for i in range(n + 1)]


def box(name, center, size, mat, physics=True, friction=0.8):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if physics:
        add_rigid(o, 'PASSIVE', friction=friction, bounce=0.05)
    return o


def lean(obj, deg=14):
    """맨 앞 도미노를 앞 아래 모서리를 축으로 살짝 기울여 연쇄 시작 (컷으로 이어지는 장면 시작용)."""
    bpy.context.view_layer.update()
    sc = obj.dimensions.z / DOM_H
    mw = obj.matrix_world.copy()
    edge = mw @ Vector((0, DOM_T * sc / 2, -DOM_H * sc / 2))
    axis = (mw.to_3x3() @ Vector((1, 0, 0))).normalized()
    R = Matrix.Translation(edge) @ Matrix.Rotation(-math.radians(deg), 4, axis) @ Matrix.Translation(-edge)
    obj.matrix_world = R @ mw


# ---------- 바닥 / 조명 / 배경 ----------
def wood_floor(size=60):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = 'Floor'
    floor.data.materials.append(wood_mat())
    add_rigid(floor, 'PASSIVE', friction=0.8, shape='MESH')
    return floor


def night_lighting(scene):
    """보름달 밤 + 따뜻한 등불 조명."""
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    moon = bpy.context.object
    moon.name = 'MoonLight'
    moon.data.energy = 1.2
    moon.data.color = (0.75, 0.82, 1.0)
    moon.data.angle = math.radians(3)
    moon.rotation_euler = (math.radians(50), math.radians(-15), math.radians(-35))
    bpy.ops.object.light_add(type='AREA', location=(-4, -3, 6))
    key = bpy.context.object
    key.name = 'LanternKey'
    key.data.energy = 900
    key.data.size = 5
    key.data.color = (1.0, 0.78, 0.5)
    key.rotation_euler = (math.radians(35), math.radians(-30), 0)
    bpy.ops.object.light_add(type='AREA', location=(5, 6, 4))
    rim = bpy.context.object
    rim.name = 'Rim'
    rim.data.energy = 500
    rim.data.size = 6
    rim.data.color = (0.8, 0.85, 1.0)
    rim.rotation_euler = (math.radians(-50), math.radians(40), 0)

    world = scene.world or bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.01, 0.018, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0


def camera(loc, target, lens=35, dof_fstop=2.8):
    bpy.ops.object.empty_add(location=target)
    tgt = bpy.context.object
    tgt.name = 'CamTarget'
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.data.lens = lens
    con = cam.constraints.new('TRACK_TO')
    con.target = tgt
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    if dof_fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = tgt
        cam.data.dof.aperture_fstop = dof_fstop
    bpy.context.scene.camera = cam
    return cam, tgt


# ---------- 렌더 ----------
def is_cloud():
    """GPU 없는 환경(클라우드)이면 True → Cycles CPU로 미리보기."""
    return os.environ.get('DOMINO_PREVIEW_CPU') == '1'


def render_setup(scene, preview=False):
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.render.resolution_percentage = 50 if preview else 100
    if is_cloud():
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 24 if preview else 128
        scene.cycles.use_denoising = True
    else:
        for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
            try:
                scene.render.engine = eng
                break
            except TypeError:
                pass
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'


def render_still(scene, frame, path):
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.frame_set(frame)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---------- 물리 검증 ----------
def tilt(obj):
    """(기울기 각도, 앞으로 넘어졌는지). 앞 = 자기 +Y 방향."""
    m = obj.matrix_world.to_3x3()
    up = m @ Vector((0, 0, 1))
    ang = math.degrees(math.acos(max(-1.0, min(1.0, up.z))))
    return ang, up


def verify(scene, objs, every=15, forward_fn=None):
    """프레임을 진행하며 쓰러진 개수 출력. 끝에서 서 있는/뒤로 넘어진 도미노 목록 반환."""
    rest = {o.name: o.matrix_world.to_3x3() @ Vector((0, 1, 0)) for o in objs}
    first_fall = {}
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        for o in objs:
            if o.name not in first_fall:
                ang, _ = tilt(o)
                if ang > 10:
                    first_fall[o.name] = f
        if f % every == 0 or f == scene.frame_end:
            print(f'  f{f:4d}  쓰러짐 {len(first_fall):4d}/{len(objs)}')
    standing, backward = [], []
    for o in objs:
        ang, up = tilt(o)
        if ang < 45:
            standing.append(o.name)
        elif up.dot(rest[o.name]) < 0:
            backward.append(o.name)
    print(f'  결과: 서 있음 {len(standing)}, 뒤로 넘어짐 {len(backward)}')
    if standing:
        print('  서 있는 것:', standing[:10])
    if backward:
        print('  뒤로 넘어진 것:', backward[:10])
    return standing, backward, first_fall


# =========================================================
#  편집용 클립 만들기: 카메라 따라가기, 영상 렌더, 쓰러짐 소리
# =========================================================
def fall_times(scene, objs, deg=10):
    """물리가 이미 계산된 뒤, 각 오브젝트가 처음 기울기 deg를 넘은 프레임."""
    first = {}
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        for o in objs:
            if o.name not in first and tilt(o)[0] > deg:
                first[o.name] = f
    return first


def positions_by_frame(scene, obj):
    out = {}
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        out[f] = obj.matrix_world.translation.copy()
    return out


def front_by_frame(scene, objs, first):
    """연쇄의 '앞머리' 위치: 그 프레임까지 쓰러지기 시작한 것 중 가장 최근 도미노의 처음 자리."""
    scene.frame_set(scene.frame_start)
    start = {o.name: o.matrix_world.translation.copy() for o in objs}
    order = sorted((f, n) for n, f in first.items())
    out, k, cur = {}, 0, start[objs[0].name]
    for f in range(scene.frame_start, scene.frame_end + 1):
        while k < len(order) and order[k][0] <= f:
            cur = start[order[k][1]]
            k += 1
        out[f] = cur.copy()
    return out


def bake_camera(scene, target_by_frame, offset, smooth=15, every=3):
    """카메라가 target을 부드럽게 따라가도록 키프레임 (offset = 카메라 - 목표)."""
    cam = scene.camera
    tgt = bpy.data.objects['CamTarget']
    frames = sorted(target_by_frame)
    pts = [target_by_frame[f] for f in frames]
    offset = Vector(offset)
    for i in range(0, len(frames), every):
        lo, hi = max(0, i - smooth), min(len(pts), i + smooth + 1)
        avg = sum((p for p in pts[lo:hi]), Vector()) / (hi - lo)
        tgt.location = avg
        tgt.keyframe_insert('location', frame=frames[i])
        cam.location = avg + offset
        cam.keyframe_insert('location', frame=frames[i])


def render_clip(scene, path_mp4, f0, f1, samples=6):
    """f0~f1 프레임을 mp4로. 클라우드(DOMINO_PREVIEW_CPU=1)는 PNG로 뽑아 imageio-ffmpeg로 묶고,
    PC는 Blender 자체 FFMPEG 출력으로 바로 저장."""
    os.makedirs(os.path.dirname(path_mp4), exist_ok=True)
    scene.frame_start, scene.frame_end = f0, f1
    if is_cloud():
        scene.cycles.samples = samples
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.max_bounces = 4             # 미리보기 속도: 빛 반사 횟수 줄임
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 4
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False
        tmp = path_mp4[:-4] + '_frames'
        os.makedirs(tmp, exist_ok=True)
        scene.render.image_settings.media_type = 'IMAGE'
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = os.path.join(tmp, 'f_')
        bpy.ops.render.render(animation=True)
        import imageio_ffmpeg, subprocess, shutil
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(scene.render.fps),
                        '-start_number', str(f0), '-i', os.path.join(tmp, 'f_%04d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', path_mp4], check=True)
        shutil.rmtree(tmp)
    else:
        try:
            scene.render.image_settings.media_type = 'VIDEO'
        except (AttributeError, TypeError):
            pass
        scene.render.image_settings.file_format = 'FFMPEG'
        scene.render.ffmpeg.format = 'MPEG4'
        scene.render.ffmpeg.codec = 'H264'
        scene.render.ffmpeg.constant_rate_factor = 'HIGH'
        scene.render.filepath = path_mp4
        bpy.ops.render.render(animation=True)


def write_clicks_wav(first, sizes, fps, f0, f1, path, seed=1):
    """도미노가 맞은 순간마다 '딱' 소리 (크기가 클수록 낮고 크게). 44.1kHz 모노 wav."""
    import numpy as np, wave
    sr = 44100
    n = int((f1 - f0 + 1) / fps * sr) + sr
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(seed)
    for name, f in first.items():
        if not (f0 <= f <= f1):
            continue
        sc = sizes.get(name, 1.0)
        t0 = int((f - f0) / fps * sr + rng.integers(0, int(sr / fps)))
        L = int(0.05 * sr)
        tt = np.arange(L) / sr
        freq = 2400 / sc * rng.uniform(0.85, 1.15)
        click = (np.sin(2 * np.pi * freq * tt) * 0.6 + rng.normal(0, 0.4, L)) * np.exp(-tt * 90)
        click *= 0.25 * min(sc, 2.0) * rng.uniform(0.7, 1.0)
        out[t0:t0 + L] += click[:max(0, min(L, n - t0))]
    peak = np.abs(out).max()
    if peak > 0.9:
        out *= 0.9 / peak
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def write_bell_wav(path, dur=4.0):
    """마무리 종소리 (여러 배음이 천천히 사라지는 풍경 소리)."""
    import numpy as np, wave
    sr = 44100
    t = np.arange(int(dur * sr)) / sr
    base = 880
    sig = np.zeros_like(t)
    for mult, amp, decay in [(1, 1.0, 1.2), (2.76, 0.5, 1.8), (5.4, 0.25, 2.6), (8.9, 0.12, 3.5), (0.5, 0.3, 0.9)]:
        sig += amp * np.sin(2 * np.pi * base * mult * t) * np.exp(-t * decay)
    sig *= np.minimum(1, t * 200) * 0.35
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((sig * 32767).astype(np.int16).tobytes())
