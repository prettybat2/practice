# =========================================================
#  60초 완성본 편집: edit_package/clips + audio → edit_package/final/domino_chuseok_60s.mp4
#  - 구간 자르기, 속도 조절(슬로모션은 중간 프레임 생성), 장면 사이 짧은 크로스페이드
#  - 도미노 소리(장면별 wav)를 영상과 같이 자르고 늘림
#  - 마지막: 그림 벽 공개 → 원본 그림으로 부드럽게 전환 + 천천히 확대 + 종소리
#  실행: python3 scripts/edit_video.py        (Blender 필요 없음, imageio-ffmpeg 사용)
#  구간을 바꾸려면 아래 TIMELINE만 고치면 됨
# =========================================================
import os, subprocess, json, shutil
import imageio_ffmpeg

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(HERE, 'edit_package')
CLIPS, AUDIO = os.path.join(PKG, 'clips'), os.path.join(PKG, 'audio')
OUT = os.path.join(PKG, 'final')
TMP = os.path.join(OUT, '_tmp')
FF = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
XF = 0.35           # 장면 사이 크로스페이드 (초)

# (클립 이름, 시작초, 끝초, 속도)  속도 0.5 = 2배 슬로모션
TIMELINE = [
    ('scene01_marble',        0.0, 5.0, 1.6),    # 나선 레일: 빠르게 훑기
    ('scene01_marble',        5.0, 9.6, 1.0),    # 깔때기 소용돌이
    ('scene01_marble',        9.6, 11.2, 0.5),   # 시소에 떨어지는 순간 슬로모션
    ('scene01_marble',       11.2, 14.5, 1.0),   # 첫 도미노 줄
    ('scene02_stairs_bridge', 0.0, 4.5, 1.3),    # S자 → U턴
    ('scene02b_overview',     0.0, 2.5, 1.0),    # 부감: 다리 교차
    ('scene02_stairs_bridge', 4.5, 7.6, 1.0),    # 계단 오르내리기
    ('scene03_pyramid',       0.0, 1.8, 1.0),    # 쐐기 → 피라미드
    ('scene03_pyramid',       1.8, 4.0, 0.5),    # 피라미드 붕괴 슬로모션
    ('scene04a_yut_front',    0.0, 2.3, 1.0),    # 윷가락으로 다가감
    ('scene04b_yut_top',      0.4, 3.6, 1.0),    # 위에서 "윷!"
    ('scene05_moon',          0.0, 13.0, 2.0),   # 보름달 나선 (빠르게)
    ('scene05_moon',         13.0, 15.0, 1.0),   # 달 완성 여운
    ('scene06_y_split',       0.0, 4.3, 1.0),    # Y자 분기 → 구슬 출발
    ('scene07a_wall_fall',    0.0, 3.0, 0.5),    # 구슬이 모서리를 침 슬로모션
    ('scene07a_wall_fall',    3.0, 11.0, 1.0),   # V자로 번지는 그림 벽
    ('scene07b_wall_reveal',  0.0, 3.0, 1.0),    # 위에서 본 공개
]
PICTURE = os.path.join(HERE, 'assets', 'chuseok_cats.png')
PICTURE_SEC = 5.0


def run(args):
    subprocess.run([FF, '-y', '-loglevel', 'error'] + args, check=True)


def probe_dur(path):
    out = subprocess.run([FF, '-i', path], capture_output=True, text=True).stderr
    for line in out.splitlines():
        if 'Duration' in line:
            h, m, s = line.split('Duration:')[1].split(',')[0].strip().split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def atempo_chain(speed):
    """atempo는 0.5~2.0만 되므로 여러 번 이어 붙임."""
    parts, s = [], speed
    while s < 0.5:
        parts.append('atempo=0.5'); s /= 0.5
    while s > 2.0:
        parts.append('atempo=2.0'); s /= 2.0
    parts.append(f'atempo={s:.4f}')
    return ','.join(parts)


def make_segment(i, name, t0, t1, speed, size):
    src = os.path.join(CLIPS, f'{name}.mp4')
    wav = os.path.join(AUDIO, f'{name}.wav')
    dur = probe_dur(src)
    t1 = min(t1, dur)
    if t1 - t0 < 0.3:
        print(f'  건너뜀: {name} {t0}~{t1} (클립 길이 {dur:.1f}초)')
        return None
    vf = f'trim={t0}:{t1},setpts=(PTS-STARTPTS)/{speed},scale={size}'
    if speed < 1.0:     # 슬로모션: 움직임 보간으로 중간 프레임 생성
        vf += f",minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1"
    else:
        vf += f',fps={FPS}'
    out = os.path.join(TMP, f'seg{i:02d}.mp4')
    args = ['-i', src]
    if os.path.exists(wav):
        args += ['-i', wav]
        af = f'atrim={t0}:{t1},asetpts=PTS-STARTPTS,{atempo_chain(speed)},aresample=44100,aformat=channel_layouts=stereo'
        args += ['-filter_complex', f'[0:v]{vf}[v];[1:a]{af}[a]', '-map', '[v]', '-map', '[a]']
    else:
        args += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                 '-filter_complex', f'[0:v]{vf}[v]', '-map', '[v]', '-map', '1:a', '-shortest']
    run(args + ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-c:a', 'aac', '-b:a', '160k', out])
    return out


def make_picture(size):
    """원본 그림: 세로 화면에 맞춰 천천히 확대 + 종소리."""
    w, h = map(int, size.split(':'))
    n = int(PICTURE_SEC * FPS)
    out = os.path.join(TMP, 'picture.mp4')
    W2, H2 = w * 2, h * 2
    # 그림 비율(0.8)이 세로 화면(0.56)보다 넓으므로: 흐린 확대 그림을 배경으로 깔고 가운데에 원본
    vf = (f'split[a][b];[a]scale={W2}:{H2}:force_original_aspect_ratio=increase,crop={W2}:{H2},boxblur=30:3,eq=brightness=-0.08[bg];'
          f'[b]scale={W2}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,'
          f"zoompan=z='min(1+0.0012*on,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={w}x{h}:fps={FPS}")
    run(['-loop', '1', '-i', PICTURE, '-i', os.path.join(AUDIO, 'bell.wav'),
         '-filter_complex', f'[0:v]{vf}[v];[1:a]apad,atrim=0:{PICTURE_SEC},aformat=channel_layouts=stereo[a]',
         '-map', '[v]', '-map', '[a]', '-t', str(PICTURE_SEC),
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-c:a', 'aac', out])
    return out


def join(segs, out):
    """크로스페이드로 이어 붙이기."""
    durs = [probe_dur(s) for s in segs]
    args = []
    for s in segs:
        args += ['-i', s]
    fc, v, a, t = [], '[0:v]', '[0:a]', durs[0]
    for k in range(1, len(segs)):
        fc.append(f'{v}[{k}:v]xfade=transition=fade:duration={XF}:offset={t - XF:.3f}[v{k}]')
        fc.append(f'{a}[{k}:a]acrossfade=d={XF}[a{k}]')
        v, a = f'[v{k}]', f'[a{k}]'
        t += durs[k] - XF
    run(args + ['-filter_complex', ';'.join(fc), '-map', v, '-map', a,
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', out])
    return t


if __name__ == '__main__':
    os.makedirs(TMP, exist_ok=True)
    first = next(os.path.join(CLIPS, f'{n}.mp4') for n, *_ in TIMELINE
                 if os.path.exists(os.path.join(CLIPS, f'{n}.mp4')))
    info = subprocess.run([FF, '-i', first], capture_output=True, text=True).stderr
    import re
    m = re.search(r'Video:.*?(\d{3,5})x(\d{3,5})', info)
    size = f'{m.group(1)}:{m.group(2)}'
    segs = []
    for i, (name, t0, t1, sp) in enumerate(TIMELINE):
        if not os.path.exists(os.path.join(CLIPS, f'{name}.mp4')):
            print(f'  없음: {name}')
            continue
        print(f'  구간 {i:02d} {name} {t0}~{t1}초 x{sp}', flush=True)
        s = make_segment(i, name, t0, t1, sp, size)
        if s:
            segs.append(s)
    segs.append(make_picture(size))
    final = os.path.join(OUT, 'domino_chuseok_60s.mp4')
    total = join(segs, final)
    shutil.rmtree(TMP)
    print(f'완성: {final}  ({total:.1f}초, {size.replace(":", "x")})')
