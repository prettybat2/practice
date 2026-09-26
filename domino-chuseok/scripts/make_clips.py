# =========================================================
#  편집용 클립 만들기: 장면마다 물리 계산 → 카메라 연출 → 영상 + 쓰러짐 소리
#  결과: edit_package/clips/*.mp4, edit_package/audio/*.wav
#  실행: blender -b -P scripts/make_clips.py -- scene01 scene03   (고를 수 있음, 없으면 전부)
#        클라우드 미리보기: DOMINO_PREVIEW_CPU=1 python3 scripts/make_clips.py -- scene01
# =========================================================
import bpy, math, os, sys, runpy, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import domino_lib as D
from mathutils import Vector

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(HERE, 'scripts')
PKG = os.path.join(HERE, 'edit_package')
CLIPS, AUDIO = os.path.join(PKG, 'clips'), os.path.join(PKG, 'audio')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def run_scene(fname):
    """장면 스크립트 실행 (물리 계산까지 끝남). 그 안의 변수들을 돌려줌."""
    sys.argv = [fname]              # 장면 스크립트가 렌더 옵션을 보지 않도록
    with contextlib.redirect_stdout(io.StringIO()):
        g = runpy.run_path(os.path.join(SCRIPTS, fname))
    scene = bpy.context.scene
    D.render_setup(scene, preview=D.is_cloud())
    return g, scene


def dominoes(scene):
    return [o for o in scene.objects if o.get('domino')]


def sound(scene, name, first, f0, f1):
    sizes = {o.name: o.dimensions.z for o in dominoes(scene)}
    D.write_clicks_wav(first, sizes, scene.render.fps, f0, f1, os.path.join(AUDIO, f'{name}.wav'))


def clip(scene, name, f0, f1, first=None):
    print(f'[{name}] 프레임 {f0}~{f1} 렌더', flush=True)
    if first is not None:
        sound(scene, name, first, f0, f1)
    D.render_clip(scene, os.path.join(CLIPS, f'{name}.mp4'), f0, f1)


def last_fall(first, pad=20):
    return max(first.values()) + pad


# ---------- 장면별 연출 ----------
def scene01():
    g, sc = run_scene('scene01_marble_seesaw.py')
    ball = g['ball']
    doms = dominoes(sc)
    first = D.fall_times(sc, doms)
    track = D.positions_by_frame(sc, ball)
    # 구슬을 비스듬히 위에서 따라감 (나선 → 깔때기 → 시소)
    D.bake_camera(sc, track, offset=(3.2, -4.2, 2.4), smooth=12)
    sc.camera.data.lens = 30
    clip(sc, 'scene01_marble', 1, last_fall(first), first)


def scene02():
    g, sc = run_scene('scene02_stairs_bridge.py')
    doms = g['dominoes']
    first = D.fall_times(sc, doms)
    D.bake_camera(sc, D.front_by_frame(sc, doms, first), offset=(4.5, -6.0, 4.5), smooth=20)
    sc.camera.data.lens = 28
    clip(sc, 'scene02_stairs_bridge', 1, last_fall(first), first)
    # 전체 부감 컷 (교차가 한눈에 보이게)
    sc.camera.animation_data_clear()
    bpy.data.objects['CamTarget'].animation_data_clear()
    sc.camera.location = (1.5, -14.0, 11.0)
    bpy.data.objects['CamTarget'].location = (1.6, 1.0, 0.0)
    sc.camera.data.lens = 24
    clip(sc, 'scene02b_overview', 150, last_fall(first), None)


def scene03():
    g, sc = run_scene('scene03_pyramid.py')
    first = D.fall_times(sc, dominoes(sc))
    clip(sc, 'scene03_pyramid', 1, last_fall(first, 30), first)


def scene04():
    g, sc = run_scene('scene04_yut.py')
    first = D.fall_times(sc, dominoes(sc))
    yy = g['Y_YUT']
    cam, tgt = sc.camera, bpy.data.objects['CamTarget']
    # 앞에서 낮게: 갈래가 다가오고 윷가락 등만 보임
    cam.location = (1.5, yy + 7, 1.6); tgt.location = (0, yy, 1.0); cam.data.lens = 35
    clip(sc, 'scene04a_yut_front', 1, 70, first)
    # 위에서: "윷" 공개
    cam.location = (0.01, yy + 1.3, 8.5); tgt.location = (0, yy + 1.3, 0); cam.data.lens = 40
    clip(sc, 'scene04b_yut_top', 50, 160, first)


def scene05():
    g, sc = run_scene('scene05_moon_spiral.py')
    first = D.fall_times(sc, dominoes(sc))
    clip(sc, 'scene05_moon', 1, last_fall(first, 40), first)


def scene06():
    g, sc = run_scene('scene06_y_split.py')
    first = D.fall_times(sc, dominoes(sc))
    cam, tgt = sc.camera, bpy.data.objects['CamTarget']
    cam.location = (0.0, -6.0, 7.5); tgt.location = (0.0, 3.8, 0.6); cam.data.lens = 26
    clip(sc, 'scene06_y_split', 1, 130, first)


def scene07():
    g, sc = run_scene('scene07_picture_wall.py')
    doms = dominoes(sc)
    first = D.fall_times(sc, doms)
    end = last_fall(first, 40)
    clip(sc, 'scene07a_wall_fall', 1, end, first)
    # 위에서 본 공개 컷
    Y_TOP = g['Y_TOP']
    cam, tgt = sc.camera, bpy.data.objects['CamTarget']
    tgt.location = (0, Y_TOP * 0.45, 0)
    cam.location = (0, Y_TOP * 0.45 - 2.0, Y_TOP * 1.55)
    sc.view_settings.exposure = -1.0
    clip(sc, 'scene07b_wall_reveal', end - 90, end, None)


ALL = ['scene01', 'scene02', 'scene03', 'scene04', 'scene05', 'scene06', 'scene07']
os.makedirs(CLIPS, exist_ok=True)
os.makedirs(AUDIO, exist_ok=True)
D.write_bell_wav(os.path.join(AUDIO, 'bell.wav'))
# 한 번에 한 장면만 (장면마다 장면 전체를 새로 만들기 때문에 프로세스를 나눠 돌림)
todo = [a for a in ARGS if a in ALL]
if len(todo) != 1:
    print('장면 하나를 골라 주세요. 예: -- scene01   (전부는 render_all_clips.bat / .sh)')
    sys.exit(1)
globals()[todo[0]]()
print('끝', flush=True)
