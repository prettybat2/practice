# =========================================================
#  장면 4 (23–28초): 한 줄 → 네 갈래로 벌어짐 → 윷가락 4개가 멍석 위로 쓰러짐 → "윷!"
#  윷가락은 둥근 등이 앞, 무늬 있는 평평한 배가 뒤 → 앞으로 넘어지면 배(무늬)가 위로 = 윷
#  실행: blender -b -P scripts/scene04_yut.py              (물리 검증)
#        blender -b -P scripts/scene04_yut.py -- render 1 60
# =========================================================
import bpy, bmesh, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAMES = 200
scene = D.reset_scene(frames=FRAMES, time_scale=2.5)
D.wood_floor()

GAP, COL = 0.6, 0.55
YUT_H, YUT_W, YUT_T = 2.3, 0.6, 0.3
YUT_X = [(i - 1.5) * 1.15 for i in range(4)]     # 윷가락 4개 가로 위치


# ---------- 재질 ----------
def yut_back_mat():
    """둥근 등: 밝은 박달나무."""
    m = D.simple_mat('YutBack', (0.42, 0.2, 0.08), rough=0.35, coat=0.6)
    return m

def yut_face_mat():
    """평평한 배: 조금 더 밝은 나무 + 인두로 지진 X 무늬 세 개."""
    m = bpy.data.materials.new('YutFace')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.5
    b.inputs['Coat Weight'].default_value = 0.4
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    # X 무늬: |x| 와 |z - 중심| 이 같은 곳 근처 → 대각선 두 줄
    def node(t, **kw):
        n = nt.nodes.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        return n
    marks = None
    for zc in (-0.7, 0.0, 0.7):
        dz = node('ShaderNodeMath', operation='SUBTRACT'); dz.inputs[1].default_value = zc
        nt.links.new(sep.outputs['Z'], dz.inputs[0])
        adz = node('ShaderNodeMath', operation='ABSOLUTE'); nt.links.new(dz.outputs[0], adz.inputs[0])
        adx = node('ShaderNodeMath', operation='ABSOLUTE'); nt.links.new(sep.outputs['X'], adx.inputs[0])
        diff = node('ShaderNodeMath', operation='SUBTRACT')
        nt.links.new(adz.outputs[0], diff.inputs[0]); nt.links.new(adx.outputs[0], diff.inputs[1])
        ad = node('ShaderNodeMath', operation='ABSOLUTE'); nt.links.new(diff.outputs[0], ad.inputs[0])
        line = node('ShaderNodeMath', operation='LESS_THAN'); line.inputs[1].default_value = 0.04
        nt.links.new(ad.outputs[0], line.inputs[0])
        inbox = node('ShaderNodeMath', operation='LESS_THAN'); inbox.inputs[1].default_value = 0.2
        nt.links.new(adz.outputs[0], inbox.inputs[0])
        mk = node('ShaderNodeMath', operation='MULTIPLY')
        nt.links.new(line.outputs[0], mk.inputs[0]); nt.links.new(inbox.outputs[0], mk.inputs[1])
        if marks is None:
            marks = mk
        else:
            mx = node('ShaderNodeMath', operation='MAXIMUM')
            nt.links.new(marks.outputs[0], mx.inputs[0]); nt.links.new(mk.outputs[0], mx.inputs[1])
            marks = mx
    mix = node('ShaderNodeMix', data_type='RGBA')
    mix.inputs['A'].default_value = (0.9, 0.74, 0.5, 1)
    mix.inputs['B'].default_value = (0.12, 0.05, 0.02, 1)
    nt.links.new(marks.outputs[0], mix.inputs['Factor'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    return m

BACK, FACE = yut_back_mat(), yut_face_mat()


def yut_stick(x, y, name):
    """반원 기둥: 평평한 면이 -y(뒤), 둥근 등이 +y(앞)."""
    bm = bmesh.new()
    seg = 20
    prof = [(YUT_W / 2 * math.cos(math.pi * k / seg), YUT_T * math.sin(math.pi * k / seg) - YUT_T / 2)
            for k in range(seg + 1)]
    rings = []
    for zz in (-YUT_H / 2, YUT_H / 2):
        rings.append([bm.verts.new((px, py, zz)) for px, py in prof])
    bot, top = rings
    for k in range(seg):                                           # 둥근 등
        f = bm.faces.new((bot[k], bot[k + 1], top[k + 1], top[k])); f.material_index = 0
    f = bm.faces.new([bot[0], top[0], top[-1], bot[-1]]); f.material_index = 1      # 평평한 배
    bm.faces.new(list(reversed(bot))); bm.faces.new(top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    for p in me.polygons:
        p.use_smooth = p.material_index == 0 and len(p.vertices) == 4
    me.materials.append(BACK)
    me.materials.append(FACE)
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    o.location = (x, y, YUT_H / 2)
    D.add_rigid(o, 'ACTIVE', mass=D.DOM_MASS * 3.0, friction=0.7, bounce=0.05, shape='CONVEX_HULL')
    o['domino'] = True
    return o


# ---------- 들어오는 줄 + 쐐기(1→4칸) ----------
lead = [D.make_domino((0, -GAP * (4 + m), 0), 0, 1.0, D.rainbow(0.62), f'Lead_{m}') for m in range(6, 0, -1)]
D.lean(lead[0])
wedge = []
for k in range(4):
    for i in range(k + 1):
        wedge.append(D.make_domino(((i - k / 2) * COL, GAP * (k - 4), 0), 0, 1.0,
                                   D.rainbow(0.62 + 0.05 * k), f'Wedge_{k}_{i}'))

# ---------- 네 갈래로 벌어지며 커지는 줄 ----------
Y0, Y1 = 0.0, 3.4            # 벌어지기 시작 / 끝
branches, ends = [], []
for i in range(4):
    x0, x1 = (i - 1.5) * COL, YUT_X[i]
    pts = D.straight((x0, Y0, 0), (x1, Y1, 0), n=200)
    br = D.dominoes_along(pts, scale_fn=lambda u: 1.0 + 0.6 * u,
                          color_fn=lambda u, i=i: D.rainbow(0.8 + 0.06 * i + 0.1 * u),
                          prefix=f'Br{i}')
    branches += br
    ends.append(br[-1])

# ---------- 윷가락 ----------
Y_YUT = max(e.location.y for e in ends) + 0.72
sticks = [yut_stick(e.location.x, Y_YUT, f'Yut_{i}') for i, e in enumerate(ends)]

# ---------- 멍석 (짚 돗자리, 장식) ----------
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, Y_YUT + 1.2, 0.002))
mat_o = bpy.context.object
mat_o.name = 'Meongseok'
mat_o.scale = (5.2, 3.6, 1)
mm = bpy.data.materials.new('Straw')
nt = mm.node_tree
br = nt.nodes.new('ShaderNodeTexBrick')
br.inputs['Scale'].default_value = 14
br.inputs['Color1'].default_value = (0.72, 0.55, 0.28, 1)
br.inputs['Color2'].default_value = (0.62, 0.46, 0.22, 1)
br.inputs['Mortar'].default_value = (0.35, 0.24, 0.1, 1)
br.inputs['Mortar Size'].default_value = 0.01
br.inputs['Brick Width'].default_value = 0.3
br.inputs['Row Height'].default_value = 0.12
nt.links.new(br.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
nt.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
mat_o.data.materials.append(mm)

# ---------- 빠져나가는 줄: 3번째 윷가락 머리가 첫 도미노를 침 ----------
ex_start = Vector((YUT_X[2], Y_YUT + YUT_H * 0.8, 0))
exit_line = D.dominoes_along(D.straight(ex_start, ex_start + Vector((2.2, 3.0, 0)), n=100),
                             scale_fn=lambda u: 1.0, color_fn=lambda u: D.rainbow(0.1 + 0.1 * u),
                             prefix='Exit')

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
D.camera(loc=(6.0, -5.0, 5.5), target=(0, 2.4, 0.6), lens=28, dof_fstop=None)
D.render_setup(scene, preview=True)

allobjs = lead + wedge + branches + sticks + exit_line
print(f'도미노 {len(allobjs) - 4}개 + 윷가락 4개')
D.verify(scene, allobjs, every=20)

# 윷 결과: 평평한 배(로컬 -y)가 위를 보면 "배"
up_face = 0
for s in sticks:
    n = s.matrix_world.to_3x3() @ Vector((0, -1, 0))
    up_face += n.z > 0.5
names = {0: '모', 1: '도', 2: '개', 3: '걸', 4: '윷'}
print(f'  윷 결과: 배가 위로 {up_face}개 → {names[up_face]}')

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    for f in [int(a) for a in ARGS[1:]] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene04_f{f:03d}.png'))
