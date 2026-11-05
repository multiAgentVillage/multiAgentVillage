"""Render local, static product wireframes with Pillow; no network assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = Path('C:/Windows/Fonts/msyh.ttc')
BOLD = Path('C:/Windows/Fonts/msyhbd.ttc')
BG = '#eef2f5'
INK = '#1d3042'
MUTED = '#657586'
LINE = '#d9e1e8'
BLUE = '#2d5d83'
LIGHT = '#e8eff5'
GREEN = '#37725c'
ORANGE = '#956526'


def font(size=22, bold=False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def canvas(title, subtitle, width=1800, height=1150):
    im = Image.new('RGB', (width, height), BG)
    dr = ImageDraw.Draw(im)
    text(dr, (40, 25), title, 32, bold=True)
    text(dr, (40, 77), subtitle, 19, MUTED)
    return im, dr


def text(dr, xy, value, size=22, fill=INK, bold=False):
    dr.text(xy, value, font=font(size, bold), fill=fill)


def panel(dr, box, fill='white', outline=LINE, radius=14):
    dr.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def paragraph(dr, x, y, value, width, size=21, fill=MUTED, gap=9):
    line = ''
    for char in value:
        if char == '\n' or dr.textlength(line + char, font=font(size)) > width:
            text(dr, (x, y), line, size, fill)
            y += size + gap
            line = '' if char == '\n' else char
        else:
            line += char
    if line:
        text(dr, (x, y), line, size, fill)
        y += size + gap
    return y


def button(dr, box, label, primary=False, disabled=False):
    fill = BLUE if primary else ('#f0f2f4' if disabled else 'white')
    panel(dr, box, fill, fill if primary else LINE, 8)
    ft = font(20, primary)
    x0, y0, x1, y1 = box
    w = dr.textlength(label, font=ft)
    dr.text(((x0+x1-w)/2, (y0+y1-26)/2), label, font=ft,
            fill='white' if primary else (MUTED if disabled else INK))


def tag(dr, box, label, color=GREEN):
    panel(dr, box, '#f2f6f4', '#d9e5de', 8)
    text(dr, (box[0]+12, box[1]+6), label, 18, color)


def agent(dr, x, y, name, color=BLUE):
    dr.ellipse((x-17, y-17, x+17, y+17), fill=color, outline='white', width=3)
    w = dr.textlength(name, font=font(18))
    dr.rounded_rectangle((x-w/2-8, y+22, x+w/2+8, y+51), radius=5, fill='white')
    text(dr, (x-w/2, y+22), name, 18)


def workbench():
    im, d = canvas('校园涌现 / 运行工作台', 'P03 · 低保真静态原型 · 示例数据用于说明交互，不代表已实现的仿真结果')
    panel(d, (35, 123, 1765, 210))
    text(d, (58, 143), '社团活动筹备  /  实验 001', 25, bold=True)
    tag(d, (500, 145, 600, 185), '运行中')
    text(d, (635, 151), '仿真时间  09:42', 22)
    button(d, (1195, 143, 1320, 188), '暂停')
    button(d, (1335, 143, 1495, 188), '注入事件', True)
    button(d, (1510, 143, 1620, 188), '停止')
    button(d, (1634, 143, 1740, 188), '历史')

    panel(d, (35, 229, 288, 775))
    text(d, (56, 249), '角色  /  8', 24, bold=True)
    panel(d, (53, 296, 270, 337), '#f8fafc', LINE, 7)
    text(d, (65, 304), '搜索角色…', 19, MUTED)
    rows = [('林晓', '组织者 · 正在规划'), ('陈宇', '学生 · 前往图书馆'),
            ('王悦', '学生 · 等待'), ('赵宁', '学生 · 交流中'),
            ('李晴', '组织者 · 交流中'), ('周远', '学生 · 移动中'),
            ('许安', '学生 · 等待'), ('何老师', '教师 · 教学楼')]
    for i, (name, status) in enumerate(rows):
        y = 353 + i*49
        if i == 0:
            panel(d, (48, y-3, 275, y+44), LIGHT, LIGHT, 7)
        text(d, (63, y), name, 20, BLUE if i == 0 else INK, i == 0)
        text(d, (63, y+25), status, 15, MUTED)

    panel(d, (306, 229, 1238, 775))
    text(d, (328, 249), '校园地图', 24, bold=True)
    text(d, (930, 255), '选择角色或地点查看详情', 18, MUTED)
    d.rounded_rectangle((330, 299, 1212, 711), radius=15, fill='#f6f8f7')
    roads = [((492, 420), (730, 420)), ((730, 420), (1044, 420)),
             ((492, 420), (492, 600)), ((730, 420), (730, 600)),
             ((492, 600), (1044, 600)), ((1044, 420), (1044, 600))]
    for a, b in roads:
        d.line((a, b), fill='#dae1e4', width=18)
        d.line((a, b), fill='white', width=2)
    for box, title in [((370, 320, 540, 388), '宿舍'),
                       ((651, 320, 821, 388), '教学楼'),
                       ((956, 320, 1148, 388), '图书馆'),
                       ((370, 620, 540, 687), '食堂')]:
        panel(d, box, '#e8eff1', '#cad7dd', 8)
        text(d, (box[0]+22, box[1]+18), title, 22)
    panel(d, (944, 620, 1170, 687), '#f6eee3', '#d6bb96', 8)
    text(d, (964, 636), '活动室 · 已关闭', 21, ORANGE)
    agent(d, 1010, 570, '林晓')
    agent(d, 867, 420, '陈宇')
    agent(d, 710, 570, '王悦', GREEN)
    agent(d, 470, 450, '赵宁', GREEN)
    agent(d, 535, 472, '李晴')
    agent(d, 610, 600, '周远')
    agent(d, 433, 568, '许安', GREEN)
    agent(d, 737, 423, '何老师', GREEN)
    tag(d, (332, 725, 477, 759), '●  正常行动')
    tag(d, (489, 725, 660, 759), '●  正在决策', BLUE)
    text(d, (682, 733), '移动由路线与仿真时间决定', 18, MUTED)

    panel(d, (1256, 229, 1765, 775))
    text(d, (1280, 249), '林晓', 28, bold=True)
    text(d, (1371, 258), '社团组织者', 19, MUTED)
    for box, label, active in [((1278, 301, 1407, 343), '概况', True),
                               ((1418, 301, 1547, 343), '记忆', False),
                               ((1558, 301, 1739, 343), '决策记录', False)]:
        button(d, box, label, active)
    text(d, (1280, 365), '目标', 19, MUTED)
    text(d, (1280, 396), '让社团活动顺利开展', 23, bold=True)
    text(d, (1280, 443), '当前行动', 19, MUTED)
    text(d, (1280, 475), '原行动中断 → 等待新计划', 22)
    text(d, (1280, 523), '已知信息', 19, MUTED)
    paragraph(d, 1280, 556, '09:41 在活动室观察到场地关闭。\n活动原定于10:00开始。', 450, 21)
    panel(d, (1278, 641, 1743, 755), LIGHT, LIGHT, 8)
    text(d, (1294, 654), '最近决策依据', 20, bold=True)
    paragraph(d, 1294, 687, '场地不可用，准备通知其他同学。', 420, 20)
    text(d, (1294, 721), '查看触发事件  →', 18, BLUE)

    panel(d, (35, 794, 1765, 1085))
    text(d, (58, 813), '事件时间线', 24, bold=True)
    button(d, (1210, 809, 1385, 850), '全部角色  ↓')
    button(d, (1400, 809, 1580, 850), '全部类型  ↓')
    button(d, (1595, 809, 1742, 850), '查看原因')
    lines = [('09:42', '林晓', '开始重新规划', '原因：场地关闭'),
             ('09:41', '系统', '活动室关闭已生效', '由操作者提交'),
             ('09:39', '李晴 → 赵宁', '活动邀请已送达', '来自附近交流')]
    for i, (time, actor, action, cause) in enumerate(lines):
        y = 874+i*55
        d.line((58, y+42, 1740, y+42), fill=LINE, width=1)
        text(d, (62, y), time, 21, MUTED)
        text(d, (210, y), actor, 21)
        text(d, (440, y), action, 21)
        text(d, (1100, y), cause, 20, BLUE)
    text(d, (60, 1051), '参与人数 3/8    ·    模型请求 18/120    ·    降级 0 次    ·    所有数值为示例', 18, MUTED)
    text(d, (40, 1109), '交互：选角色 → 查已知信息与记忆 → 定位决策 → 跳转原因；注入事件先“已接收”，再“已生效”。', 19, MUTED)
    im.save(ROOT / 'workbench.png')


def field(d, x, y, label, value, width=449):
    text(d, (x, y), label, 20, MUTED)
    panel(d, (x, y+35, x+width, y+85), '#f9fbfc', LINE, 7)
    text(d, (x+13, y+48), value, 20)


def journey():
    im, d = canvas('从创建到回放 / 三个关键界面', 'P02 / P04 / P05 · 低保真静态原型 · 真实应用需按文档实现状态与反馈', height=1080)
    boxes = [(35, 135, 590, 980), (622, 135, 1177, 980), (1209, 135, 1764, 980)]
    for box in boxes:
        panel(d, box)
    text(d, (62, 159), '01  创建与配置', 27, bold=True)
    text(d, (650, 159), '02  注入事件', 27, bold=True)
    text(d, (1237, 159), '03  历史回放', 27, bold=True)
    for x in [62, 650, 1237]:
        d.line((x, 214, x+498, 214), fill=LINE, width=2)

    field(d, 63, 243, '实验名称', '社团活动筹备')
    field(d, 63, 352, '场景模板', '校园 / 8名角色 / 5个地点  ↓')
    text(d, (63, 464), '角色设定', 20, MUTED)
    for i, label in enumerate(['林晓  /  组织者  /  目标：活动举办',
                               '陈宇  /  学生     /  兴趣：阅读',
                               '何老师  /  教师  /  目标：指导社团']):
        panel(d, (63, 504+i*55, 513, 551+i*55), '#f8fafb', LINE, 6)
        text(d, (75, 517+i*55), label, 18)
    text(d, (65, 680), '查看全部8名角色 / 修改有限字段  →', 18, BLUE)
    field(d, 63, 726, '单次运行请求上限', '120 次  /  可调整')
    tag(d, (63, 836, 314, 874), '模型连接检查：已通过')
    button(d, (63, 902, 248, 952), '保存草稿')
    button(d, (266, 902, 513, 952), '创建运行', True)

    field(d, 650, 243, '事件模板', '场地关闭  ↓')
    field(d, 650, 352, '目标地点', '活动室  ↓')
    field(d, 650, 461, '关闭原因', '设备维护，暂时停止开放')
    panel(d, (650, 580, 1128, 716), '#f6eee3', '#dfc9aa', 9)
    paragraph(d, 668, 597, '生效后：地点立即不可进入。\n在场角色先感知关闭；其他角色需通过通知或实际观察获知。', 440, 21, ORANGE)
    button(d, (650, 742, 836, 792), '取消')
    button(d, (856, 742, 1128, 792), '提交事件', True)
    text(d, (650, 822), '提交反馈', 20, bold=True)
    text(d, (650, 858), '① 已接收  →  ② 已生效', 23, GREEN)
    paragraph(d, 650, 907, '被拒绝时保留输入并说明原因；等待期间禁止重复提交。', 465, 18)

    tag(d, (1237, 245, 1460, 285), '历史回放 / 只读', BLUE)
    text(d, (1237, 314), '社团活动筹备  /  运行001', 21, bold=True)
    panel(d, (1237, 366, 1715, 590), '#f4f7f7', LINE, 8)
    for box, label in [((1264, 391, 1426, 449), '教学楼'),
                        ((1503, 391, 1671, 449), '图书馆'),
                        ((1425, 500, 1671, 559), '活动室 · 已关闭')]:
        panel(d, box, '#e8eff1', LINE, 6)
        text(d, (box[0]+12, box[1]+14), label, 19)
    d.line((1320, 477, 1615, 477), fill='#b5c4cd', width=5)
    d.ellipse((1458, 466, 1480, 488), fill=BLUE)
    text(d, (1237, 620), '09:00 ─────●────── 10:00', 24, BLUE)
    text(d, (1237, 659), '当前 09:41  /  事件 42', 20, MUTED)
    button(d, (1237, 707, 1377, 752), '上个事件')
    button(d, (1389, 707, 1518, 752), '播放', True)
    button(d, (1530, 707, 1715, 752), '下个事件')
    text(d, (1237, 794), '活动室关闭 → 林晓重新规划', 21)
    text(d, (1237, 837), '查看当时的角色状态与已知信息  →', 18, BLUE)
    button(d, (1237, 902, 1460, 952), '导出摘要')
    button(d, (1474, 902, 1715, 952), '返回结束页')
    text(d, (40, 1013), '状态约束：配置在运行中锁定；暂停时冻结世界；停止使旧提案失效；历史回放不调用模型。', 20, MUTED)
    im.save(ROOT / 'journey.png')


if __name__ == '__main__':
    workbench()
    journey()
    for name in ('workbench.png', 'journey.png'):
        with Image.open(ROOT / name) as im:
            print(f'{name}: {im.size[0]}x{im.size[1]}')
