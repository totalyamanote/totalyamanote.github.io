"""アウトドア比較記事を「機能性・デザイン」軸に書き換える一回きりのスクリプト（2026-11-18 坂田さん指示）。
価格ブロック（<div class=item>…）・購入ボタン・<!--op:…-->は触らない。"""
import re
from pathlib import Path

ART = Path(__file__).resolve().parent.parent / "articles" / "outdoor-brands-2026.html"
s = ART.read_text(encoding="utf-8")

OLD_T = "アウトドアブランド比較【2026年】ノースフェイス・アークテリクス・マムートなど人気9ブランドの特徴と2万円以内の上着"
NEW_T = "アウトドアブランド比較【2026年】ノースフェイス・アークテリクスなど人気9ブランドの機能性とデザインと2万円以内の上着"
NEW_D = ("【11/18更新】ザ・ノース・フェイス・アークテリクス・マムート・パタゴニア・モンベル・コロンビア・ミレー・スノーピーク・ヘリーハンセンを、"
         "公式が説明する機能性（素材・技術）とデザインの考え方で比較。2万円以内で買える上着（楽天・Yahoo!の両方にある同じ型番）もまとめました。")
s = s.replace(OLD_T, NEW_T)
s = re.sub(r'(<meta name=description content=")[^"]*"', lambda m: m.group(1) + NEW_D + '"', s, count=1)
s = re.sub(r'(<meta property=og:description content=")[^"]*"', lambda m: m.group(1) + NEW_D + '"', s, count=1)

# 導入
s = s.replace("人気のアウトドアブランドは、<b>発祥・得意な分野・修理や保証の窓口</b>がそれぞれ違います。",
              "人気のアウトドアブランドは、<b>機能性（素材・技術）とデザインの考え方</b>がそれぞれ違います。")
s = s.replace("比べたのは次の9ブランド。公式ページで確かめた事実だけで比べています。",
              "比べたのは次の9ブランド。各社の公式ページに書かれている説明だけで比べています（性能の順位は付けていません）。")
s = s.replace("alt='人気アウトドアブランド9つの比較（2026年11月16日時点）'", "alt='人気アウトドアブランド9つの機能性とデザインの比較（2026年11月18日時点）'")
s = s.replace("<b>この情報は2026年11月16日時点のものです。</b>", "<b>この情報は2026年11月18日時点のものです。</b>")

# 目次
s = s.replace("比較表（発祥・修理・2万円以内の上着）", "比較表（機能性・デザイン・2万円以内の上着）")
s = s.replace("出典（2026年11月16日確認）", "出典（2026年11月18日確認）")

# 比較表
rows = {
    "ノースフェイス": ("自社開発の防水透湿素材 FUTURELIGHT", "登山の機能と、街で着やすいシンプルさ"),
    "アークテリクス": ("GORE-TEX採用・山岳アスリートと共同で開発", "細部まで機能で決める。街向けは別ライン（VEILANCE）"),
    "マムート": ("立体パターン Georganic 3D・GORE-TEX Pro", "山の技術を都市向けにした URBANEERING"),
    "パタゴニア": ("11/18は公式サイトが読めず未確認", "11/18は公式サイトが読めず未確認"),
    "モンベル": ("防水透湿 スーパー ドライテック・軽さ", "「Function is Beauty（機能美）」"),
    "コロンビア": ("保温 オムニヒート・防水透湿 オムニテック", "日常に広げる配色と、3通りに着られる構造"),
    "ミレー": ("独自メンブレン TYPHON（耐水圧50,000mm）", "SEMNOZ は日常に溶け込むミニマルなデザイン"),
    "スノーピーク": ("吸水速乾の Quick Dry シリーズ", "コンセプト「Home⇄Camp」・田舎に似合う服"),
    "ヘリーハンセン": ("防水透湿 HELLY TECH・LIFA・ファイバーパイル", "公式の説明は機能の歴史が中心"),
}
s = s.replace("<th>発祥</th><th>創業</th><th>修理・保証</th><th>2万円以内の上着</th>",
              "<th>機能性（公式が挙げる技術）</th><th>デザイン（公式の説明）</th><th>2万円以内の上着</th>")
def fix_row(m):
    name = m.group(1)
    f, d = rows[name]
    return f"{m.group(0)[:m.start(2)-m.start(0)]}<td>{f}</td><td>{d}</td>{m.group(3)}"
s = re.sub(r"(<th class=lab><span class=cb [^>]*>(ノースフェイス|アークテリクス|マムート|パタゴニア|モンベル|コロンビア|ミレー|スノーピーク|ヘリーハンセン)</span></th>)<td>.*?</td><td>.*?</td><td>.*?</td>(<td><!--op:|<td>公式で確認</td>)",
           lambda m: f"{m.group(1)}<td>{rows[m.group(2)][0]}</td><td>{rows[m.group(2)][1]}</td>{m.group(3)}", s)
s = s.replace("<li>創業年は各社の公式の説明によります（パタゴニアは衣料をパタゴニアの名前で出した年）。</li>",
              "<li>機能・デザインの欄は、各社の公式ページの説明をまとめたものです。数値や試験の方法は社ごとに違うため、横並びの優劣は付けていません。</li>")

# 目的別
old = s[s.index("<div class=pk>"):s.index("<p>ほかのジャンルの比較は")]
new = ("<div class=pk>"
 "<div><span>防水・透湿など素材の機能を重視したい</span><b>ザ・ノース・フェイス・ミレー・モンベル</b><p>3社とも自社の防水透湿素材（FUTURELIGHT／TYPHON／スーパー ドライテック）を公式ページで説明しています。</p></div>"
 "<div><span>山の機能で、街でも着られる見た目がいい</span><b>マムート・アークテリクス・ミレー</b><p>山の技術を街向けに広げたライン（URBANEERING／VEILANCE／SEMNOZ）が公式にあります。</p></div>"
 "<div><span>日常の服として着たい・配色も楽しみたい</span><b>コロンビア・スノーピーク</b><p>コロンビアは日常へ広げる考え方、スノーピークは「Home⇄Camp」というコンセプトを公式に掲げています。</p></div>"
 "<div><span>軽さと機能のバランスを日本のブランドで</span><b>モンベル</b><p>「Function is Beauty（機能美）」と「Light &amp; Fast（軽量と迅速）」が基本コンセプトです。O.D.パーカの公式価格は9,300円（税込）。</p></div>"
 "<div><span>海・釣り・雨の日に着たい</span><b>ヘリーハンセン</b><p>防水透湿素材 HELLY TECH など、水まわりの機能の歴史が公式ページの中心です。</p></div>"
 "</div>")
s = s.replace(old, new)
s = s.replace("この記事では<b>2万円以内の上着</b>を選んでいます。高いジャケットは、各ブランドの公式ストアで比べてください。",
              "この記事では<b>2万円以内の上着</b>を選んでいます。高いジャケット（上位モデル）の機能は、各ブランドの公式ストアで比べてください。")

# ブランド別ブロック
B = {
"b-tnf": ("素材の機能が強み。街向けのシンプルな線もある。",
  [("機能の中心","自社開発の防水透湿素材 FUTURELIGHT"),("素材の仕組み","極細の繊維を吹き重ねた3層のメンブレン（公式の説明）"),("デザイン","街向けのUrban Explorationコレクションは「機能性と都市部での利便性」が軸")],
  ["FUTURELIGHTは、繊維の隙間が水の分子より小さく、水を通さず空気を通すと公式が説明<small class=c>密度を変えて、防水性と通気性のバランスを調整</small>",
   "メンブレンが薄く軽くて柔らかく、伸縮性があると公式が説明<small class=c>通気性があるぶん、ベンチレーション（開口部）を減らせるとも</small>",
   "FL Coach Jacketのシンプルなデザインは「男女問わず幅広いスタイリングに対応」と公式が説明",
   "中わた VENTRIX の製品は「都市生活での多様な温度変化にも対応」と公式が説明"],
  "登山・クライミング・トレイルラン（用途別モデル）／街の日常着"),
"b-arc": ("山岳アスリートと作る本格派。街向けは別ライン。",
  [("機能の中心","山岳アスリートと共同で開発・テスト"),("素材","GORE-TEXを採用（公式の説明）"),("デザイン","「機能性、シンプルさ、耐久性、そして長く愛用できるデザイン」")],
  ["ブランドの方針は、山岳アスリートのニーズに応える高機能ギア<small class=c>デザイナーとアスリートが共同でテストし、コースト山脈での実地の知見を開発に使うと公式が説明</small>",
   "公式は「厳しいコンディションでは、デザインの細部が大きな意味を持つ」と説明",
   "街向けのVEILANCE（2009年〜）は、公式英語ページで「Clothing that is beautiful first, trusted to perform always」と説明<small class=c>ミニマルなデザインと洗練されたシルエットが特徴</small>",
   "2万円以内の上着は、楽天・Yahoo!で同じ型番のものが見つかりませんでした<small class=c>この記事では購入ボタンを付けていません</small>"],
  "登山・クライミング（本線）／通勤や急な雨（VEILANCE）"),
"b-mammut": ("山の動きやすさを、街の服にも持ち込むブランド。",
  [("機能の中心","立体パターン Georganic 3D"),("素材","EIGER EXTREMEは GORE-TEX Pro 3レイヤー（ePEメンブレン）"),("デザイン","街向けの URBANEERING は「洗練のデザイン」を融合")],
  ["Georganic 3Dは、動きに追随する立体パターンで「最高の動きやすさと究極の着心地」を目指す<small class=c>公式は、クライミング向けでアーバニアリングでも快適と説明</small>",
   "EIGER EXTREME 第6世代は、約95%リサイクル素材・80デニールの生地で耐摩耗性を高めたと公式が説明",
   "From Work to Climb：山岳の技術を都市に応用し、素材と縫製パターンにこだわったジャケット・バックパックを展開",
   "理念は「MOVED BY MOUNTAINS」（より早く、より軽く、より安全に、より快適に山を楽しむ）"],
  "アルピニズム・高所の山行／通勤＋日帰りハイク"),
"b-patagonia": ("公式サイトが読めなかったため、11/18は機能・デザインの説明を載せていません。",
  [("確認状況","2026年11月18日はパタゴニア公式サイトがメンテナンス中で、素材・デザインのページを確認できませんでした")],
  ["機能性（素材・防水の基準など）とデザインの考え方は、公式サイトで直接確認してください<small class=c>サイトの復旧後に、確認できた内容をこの記事に追記します</small>"],
  None),
"b-montbell": ("軽さと防水透湿の機能を、日本の価格感で。",
  [("機能の中心","防水透湿 スーパー ドライテック（3レイヤー）"),("透湿性","50,000g/m²・24hrs（JIS L-1099B-1法・参考値）"),("デザイン","「Function is Beauty（機能美）」")],
  ["スーパー ドライテックは、軽量で摩耗に強い表地・全面ストレッチ。トレントフライヤー ジャケットの平均重量は男性233g・女性209gと公式が表記<small class=c>PFAS不使用</small>",
   "スーパーメリノウールは、吸湿発熱と、一般的なメリノより繊維が長くチクチクしにくいと公式が説明<small class=c>家庭で洗濯できる</small>",
   "基本コンセプトは「Function is Beauty（機能美）」と「Light &amp; Fast（軽量と迅速）」",
   "ジャケットは、フードを3か所で調整でき、ポケットの位置がバックパックのハーネスと干渉しにくい設計（公式）"],
  "運動量の多い全天候のアクティビティ"),
"b-columbia": ("保温・防水の技術が幅広く、日常にも広げるブランド。",
  [("機能の中心","保温 オムニヒート／防水透湿 オムニテック（1991年〜）"),("オムニヒート","裏地の反射プリントで体の熱を体の近くに戻す"),("デザイン","「ドアを開ければ、そこはアウトドアだ」")],
  ["オムニヒートは、生地の透湿性を保ちながら体の熱を戻すと公式が説明<small class=c>Infinity（2021年）は金色ドットで反射効率を高めた</small>",
   "オムニテックは、水を通さず蒸れを抑える防水透湿技術（1991年）",
   "デザインの特徴として、アウターとインナーを組み合わせて3通りに着られるインターチェンジシステムを公式が紹介",
   "バガブーパーカは「大胆な配色が街着としても受け入れられた」と公式が説明"],
  "冬の防寒・雨・紫外線対策など、日常からレジャーまで"),
"b-millet": ("防水透湿メンブレンを自社で。街向けはミニマルに。",
  [("機能の中心","独自メンブレン TYPHON NOVA（延伸ポリプロピレン）"),("数値","耐水圧 50,000mm・孔の大きさ約50ナノメートル（公式）"),("デザイン","SEMNOZ：コンセプトは「A tool, and a style.」")],
  ["TYPHON NOVAは、空孔率約80%で、着用直後から湿度を逃がすよう調整していると公式が説明<small class=c>立体裁断で動きを妨げにくい設計</small>",
   "SEMNOZコレクションは、山で培った機能を保ちつつ「日常に溶け込むミニマルなデザイン」を目指すと公式が説明",
   "CLASSICシリーズは、100年の歴史を彩った色の復活と公式が紹介"],
  "登山・クライミング・トレイルラン／日常・旅行・通勤（SEMNOZ）"),
"b-snowpeak": ("機能のスペックより、暮らし方のデザインを前に出すブランド。",
  [("機能の例","Quick Dry シリーズ：吸水速乾で通気性を保つ"),("素材","東レの素材を使った交織（公式の説明）"),("デザイン","コンセプト「Home⇄Camp」")],
  ["Quick Dry（2025春夏）は、縦糸に東レの「＆＋」、横糸に原料の50%がリサイクル素材の「Primeflex」を交織<small class=c>高い通気性を保ちながら吸水速乾性を確保・非常に軽いと公式が説明</small>",
   "「Home⇄Camp」：家とテント、カフェと森林のあいだに線を引かない服づくりと公式が説明",
   "「田舎に似合う服をつくろう」。都会のモードには乗らず、着替えなくてもよい服を目指すとしています"],
  "キャンプと日常の両方"),
"b-hh": ("水まわりの機能の歴史が長いブランド。",
  [("機能の中心","防水透湿素材 HELLY TECH"),("アンダー","LIFA（ポリプロピレン製。水分を取り込まず軽く乾きやすい）"),("重ね着","ファイバーパイルとレイヤリング（重ね着）の考え方")],
  ["HELLY TECHは、防水性を保ちながら蒸れや結露を抑える独自素材<small class=c>ほかに、保温と軽さを兼ねたファイバーパイル（1961年）</small>",
   "3レイヤー・システム（1986年）の考え方を、公式が紹介",
   "デザインについての具体的な説明は、今回確認した公式ページには少なめでした<small class=c>1878年のパリ万博で船乗り向け衣料のデザイン賞を受賞（公式）</small>"],
  "セーリング・マリン／スキー・スノーボード／登山"),
}
def kv(rows_): return "<dl class=kv>" + "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in rows_) + "</dl>"
for bid, (one, kvs, pts, use) in B.items():
    i = s.index(f"<div class=site id={bid}>")
    h3_end = s.index("</h3>", i) + 5
    head = s[i:h3_end]
    nxt = [k for k in (s.find("<div class=item>", h3_end), s.find('<p class=nobuy>', h3_end)) if k != -1]
    j = min(nxt)
    old_mid = s[h3_end:j]
    warn = ""
    wm = re.search(r"<div class=warn>(.*?)</div>", old_mid, re.S)
    if wm:
        keep = [x for x in re.findall(r"<li>.*?</li>", wm.group(1)) if not re.search(r"修理|保証|リペア|返品", x)]
        if keep:
            warn = "<div class=warn><ul>" + "".join(keep) + "</ul></div>"
    use_html = f"<p class=note>向いている使い方（公式の用途説明）：{use}</p>" if use else ""
    mid = f"<p class=one>{one}</p>{kv(kvs)}<h4>機能性とデザイン</h4><ul class=pt>" + "".join(f"<li>{p}</li>" for p in pts) + f"</ul>{use_html}{warn}"
    s = s[:h3_end] + mid + s[j:]

# 見出し・FAQ
s = s.replace("<h2 id=s3 >ブランドごとの特徴と注意点</h2>", "<h2 id=s3 >ブランドごとの機能性とデザイン</h2>")
fi = s.index("<h2 id=faq >"); fj = s.index("<h2 id=src >")
faq = ("<h2 id=faq >よくある質問</h2>"
 "<h3>この記事の上着は、どうやって選びましたか？</h3><p>この記事では<b>2万円以内（販売価格）</b>の上着だけを選んでいます。楽天・Yahoo!ショッピング・Amazonのうち2つ以上で、同じ型番が売られているものです。公式ストアや正規取扱店を優先しました。</p>"
 "<h3>アークテリクスに購入ボタンがないのはなぜ？</h3><p>2万円以内で、2つ以上のストアに同じ型番がある上着が見つからなかったためです（11/16時点）。日本の価格は公式ストアで確認してください。</p>"
 "<h3>どのブランドがいちばん良いですか？</h3><p>用途で変わります。この記事では、各社の公式ページが説明する機能性（素材・技術）とデザインの考え方で比べています。性能の順位は付けていません。</p>"
 "<h3>防水の数値は、そのまま比べていいですか？</h3><p>おすすめしません。耐水圧や透湿性の数値は、各社が表記した条件・参考値で、試験の方法が社ごとに違う場合があります。数値は同じブランドの中で見るのが安心です。</p>"
 "<h3>偽物を避けるには？</h3><p>公式ストアか正規取扱店で買うのが確実です。この記事のボタンの先は、楽天・Yahoo!ショッピングの販売店の商品ページです。販売店名と「国内正規品」などの表記を確かめてから買ってください。</p>")
s = s[:fi] + faq + s[fj:]

# 出典
si = s.index("<h2 id=src >"); sj = s.index("</ul>", si) + 5
U = [
 ("ザ・ノース・フェイス（ゴールドウイン）FUTURELIGHT", "https://about.goldwin.co.jp/news/page-25495"),
 ("ザ・ノース・フェイス Urban Exploration", "https://about.goldwin.co.jp/news/page-27782"),
 ("ザ・ノース・フェイス FUTURELIGHT（シューズ特設）", "https://www.thenorthface.jp/special/futurelight-footwear/"),
 ("アークテリクス Who we are", "https://arcteryx.com/be/jp/explore/whoweare"),
 ("アークテリクス VEILANCE（英語）", "https://arcteryx.com/us/en/c/mens/veilance"),
 ("マムート EIGER EXTREME", "https://www.mammut.jp/activities/eiger"),
 ("マムート URBANEERING", "https://www.mammut.jp/news/15857"),
 ("マムート Heritage", "https://www.mammut.jp/topics/explore-heritage"),
 ("モンベル スーパー ドライテック", "https://www.montbell.jp/generalpage/disp.php?id=960"),
 ("モンベル 素材のご案内", "https://webshop.montbell.jp/material/aboutmaterial/maker/maker49.html"),
 ("モンベル 会社概要", "https://about.montbell.jp/"),
 ("モンベル O.D.パーカ Men's", "https://webshop.montbell.jp/goods/disp.php?product_id=1103320"),
 ("コロンビア オムニヒート", "https://www.columbiasports.co.jp/special/omniheat/"),
 ("コロンビア Our Story", "https://www.columbiasports.co.jp/shop/pages/ourstory.aspx"),
 ("コロンビア 名作", "https://www.columbiasports.co.jp/shop/pages/masterpiece.aspx"),
 ("ミレー TYPHON NOVA", "https://www.millet.jp/typhon/nova/"),
 ("ミレー TYPHON", "https://www.millet.jp/typhon"),
 ("ミレー 公式", "https://www.millet.jp/en"),
 ("スノーピーク アパレル", "https://www.snowpeak.co.jp/business/apparel/"),
 ("スノーピーク Quick Dry", "https://www.snowpeak.co.jp/sp/quickdry/"),
 ("ヘリーハンセン ABOUT", "https://www.hellyhansen.jp/about/"),
 ("ヘリーハンセン HISTORY", "https://www.hellyhansen.jp/history/"),
]
src = "<h2 id=src >出典（2026年11月18日確認）</h2><ul class=src>" + "".join(
    f"<li>{n}：<a href='{u}' rel=noopener target=_blank>{u}</a></li>" for n, u in U) + "<li>パタゴニア：2026年11月18日は公式サイトがメンテナンス中で、確認できませんでした。</li></ul>"
s = s[:si] + src + s[sj:]
ART.write_text(s, encoding="utf-8")
print("ok")
