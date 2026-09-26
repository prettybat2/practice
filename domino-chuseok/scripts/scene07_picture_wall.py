# =========================================================
#  장면 7 (42–54초): 그림 도미노 벽
#  - 두 송편 구슬이 벽 뒤쪽 양 모서리의 금색 급전선을 동시에 침
#  - 급전선(45도로 비스듬히 선 도미노)이 모서리에서 가운데로 연쇄하며 각 세로줄 첫 도미노를 밀어
#    쓰러짐이 V자로 카메라 쪽으로 퍼짐
#  - 벽 도미노: 카메라를 보는 앞면 = 무지개, 뒷면 = 그림 픽셀 → 카메라 쪽으로 넘어지면 추석 그림
#  실행: blender -b -P scripts/scene07_picture_wall.py              (물리 검증)
#        blender -b -P scripts/scene07_picture_wall.py -- render 1 200
#  옵션: -- small  (가로 12칸짜리 작은 벽으로 빠르게 시험)
# =========================================================
import bpy, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMALL = 'small' in ARGS

FRAMES = 420
scene = D.reset_scene(frames=FRAMES, time_scale=2.5)
D.wood_floor(size=100)
D.FACE_EMISSION = 0.6                        # 쓰러진 뒤 그림 색이 은은하게 빛나 선명하게
BRASS = D.simple_mat('Brass', (0.85, 0.62, 0.3), rough=0.25, metal=1.0)
GOLD = (0.98, 0.7, 0.12)

COL, GAP = 0.6, 0.6                        # 옆 줄 틈 0.1 (0.05면 옆 줄에 걸려 연쇄가 멈춤)
NC = 12 if SMALL else 50                    # 가로 칸
NR = 14 if SMALL else 62                    # 세로 줄 (그림 비율 1122:1402 ≈ 0.8에 맞춤)
W = (NC - 1) * COL
Y_TOP = (NR - 1) * GAP                      # 맨 뒤 줄(그림 윗부분) y. 카메라는 -y 쪽
YAW_TO_CAM = math.pi                        # 벽 도미노는 -y(카메라 쪽)으로 쓰러짐


# ---------- 그림 픽셀 ----------
def load_pixels(path, nc, nr):
    """그림을 nc×nr 칸으로 평균 내어 선형 색으로 반환. [행(위→아래)][열(왼→오)]."""
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]   # 위가 0행
    out = np.zeros((nr, nc, 3), dtype=np.float32)
    for r in range(nr):
        y0, y1 = int(r * h / nr), int((r + 1) * h / nr)
        for c in range(nc):
            x0, x1 = int(c * w / nc), int((c + 1) * w / nc)
            out[r, c] = px[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)
    # sRGB → 선형 (오브젝트 색은 선형으로 쓰임)
    out = np.where(out <= 0.04045, out / 12.92, ((out + 0.055) / 1.055) ** 2.4)
    return out

PIX = load_pixels(os.path.join(HERE, 'assets', 'chuseok_cats.png'), NC, NR)

# ---------- 벽 ----------
wall = []
for r in range(NR):                 # r=0 맨 뒤(그림 윗줄) → r=NR-1 맨 앞(그림 아랫줄)
    y = Y_TOP - r * GAP
    for c in range(NC):
        x = -W / 2 + c * COL        # 카메라(-y)에서 봤을 때 왼→오
        front = D.rainbow(0.02 + 0.8 * (c / (NC - 1) * 0.6 + r / (NR - 1) * 0.4))
        wall.append(D.make_domino((x, y, 0), YAW_TO_CAM, 1.0, front, f'W_{r:02d}_{c:02d}',
                                  face_rgb=tuple(PIX[r, c])))

# ---------- 금색 급전선 (벽 뒤, 45도로 비스듬히) ----------
Y_FEED = Y_TOP + 0.5
FEED_SHIFT = 0.45
FEED_SCALE = 1.3                            # 급전선은 크게: 벽 첫 줄을 힘 있게 침
feeder = []
for c in range(NC):
    x = -W / 2 + c * COL
    side = -1 if x < 0 else 1                       # 왼쪽 절반은 +x쪽(가운데)으로, 오른쪽은 -x쪽으로
    # 쓰러지는 방향: 가운데 쪽 + 카메라 쪽(-y)으로 45도
    d = Vector((-side, -1, 0)).normalized()
    yaw = math.atan2(-d.x, d.y)
    # 45도로 넘어지면 머리가 가운데 쪽으로 약 0.6 치우쳐 닿으므로, 한 칸 바깥에 세워야 자기 줄을 침
    feeder.append(D.make_domino((x + side * FEED_SHIFT, Y_FEED, 0), yaw, FEED_SCALE, GOLD, f'Feed_{c:02d}'))

# 모서리 바깥 리드: 구슬 방향(+x/-x)에서 45도로 서서히 돌아감
leads, balls = [], []
BALL_RGB = {-1: (0.95, 0.45, 0.6), 1: (0.55, 0.85, 0.35)}
for side in (-1, 1):
    xe = side * (W / 2 + FEED_SHIFT)
    seq = []
    for k in range(1, 4):                            # 바깥쪽으로 3개, 각도 0 → 45도
        a = math.radians(45 * (3 - k) / 3)           # k=1이 급전선 옆(45도에 가까움)
        d = Vector((-side * math.cos(a), -math.sin(a), 0)).normalized()
        yaw = math.atan2(-d.x, d.y)
        seq.append(D.make_domino((xe + side * COL * k, Y_FEED, 0), yaw, FEED_SCALE - 0.1 * k, GOLD, f'Lead_{side}_{k}'))
    leads += seq
    # 구슬 + 경사로 (벽 옆 바깥에서 가운데 쪽으로 굴러옴)
    R = 0.3
    x_ball_end = xe + side * (COL * 3 + 0.75)
    RAMP_L, RAMP_H = 3.5, 0.9
    ang = math.atan2(RAMP_H, RAMP_L)
    rc = Vector((x_ball_end + side * RAMP_L / 2, Y_FEED, RAMP_H / 2))
    for dy, w, hgt, dz in [(0, 0.8, 0.08, -0.04), (-0.42, 0.06, 0.2, 0.06), (0.42, 0.06, 0.2, 0.06)]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=rc + Vector((0, dy, dz)))
        rp = bpy.context.object
        rp.name = f'Ramp_{side}'
        rp.scale = (math.hypot(RAMP_L, RAMP_H), w, hgt)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        rp.rotation_euler = (0, -side * ang, 0)     # 바깥쪽이 높음
        rp.data.materials.append(BRASS)
        D.add_rigid(rp, 'PASSIVE', friction=0.5)
    top = Vector((x_ball_end + side * (RAMP_L - 0.3), Y_FEED, RAMP_H * (RAMP_L - 0.3) / RAMP_L + R + 0.02))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=48, ring_count=24, location=top)
    b = bpy.context.object
    b.name = f'Ball_{side}'
    bpy.ops.object.shade_smooth()
    b.data.materials.append(D.glass_marble_mat(BALL_RGB[side]))
    D.add_rigid(b, 'ACTIVE', mass=0.3, friction=0.4, bounce=0.1, shape='SPHERE')
    balls.append(b)

# ---------- 조명 / 카메라 ----------
D.night_lighting(scene)
D.camera(loc=(0.0, -0.45 * Y_TOP - 6, 0.9 * Y_TOP + 6), target=(0.0, Y_TOP * 0.45, 0.0),
         lens=28, dof_fstop=None)
D.render_setup(scene, preview=True)

print(f'벽 {NC}×{NR} = {len(wall)}개, 급전선 {len(feeder)}개, 리드 {len(leads)}개')
import time
t = time.time()
D.verify(scene, wall + feeder + leads, every=30)
print(f'  물리 계산 {time.time() - t:.0f}초')
print('  급전선 쓰러짐:', ''.join('O' if D.tilt(f)[0] > 45 else '.' for f in feeder),
      ' 리드:', ''.join('O' if D.tilt(f)[0] > 45 else '.' for f in leads))
print('  첫 줄 쓰러짐: ', ''.join('O' if D.tilt(w)[0] > 45 else '.' for w in wall[:NC]))

if 'render' in ARGS:
    out = os.path.join(HERE, 'renders')
    tag = '_small' if SMALL else ''
    for f in [int(a) for a in ARGS if a.isdigit()] or [1]:
        D.render_still(scene, f, os.path.join(out, f'scene07{tag}_f{f:03d}.png'))
    if 'top' in ARGS:
        # 공개 컷: 거의 위에서 내려다봄 (그림이 똑바로 읽히게)
        cam = scene.camera
        tgt = bpy.data.objects['CamTarget']
        tgt.location = (0, Y_TOP * 0.45, 0)
        cam.location = (0, Y_TOP * 0.45 - 2.0, Y_TOP * 1.55)
        scene.view_settings.exposure = -1.0
        D.render_still(scene, FRAMES, os.path.join(out, f'scene07{tag}_top_f{FRAMES:03d}.png'))
