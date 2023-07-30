from imgkit import from_string
from typing import List


def table(
    days: List[str],
    tmin: List[float],
    tmax: List[float],
    rh: List[float],
    wind: List[float],
    rain: List[float],
    output: str = "table.png",
) -> None:
    if not len(days) == len(tmin) == len(tmax) == len(rh) == len(wind) == len(rain):
        raise ValueError("All lists must be the same length.")
    rows = len(days)
    style = """
<style type="text/css">
.tg  {border-collapse:collapse;border-color:#aabcfe;border-spacing:0;}
.tg td{background-color:#e8edff;border-color:#aabcfe;border-style:solid;border-width:1px;color:#669;
  font-family:Arial, sans-serif;font-size:14px;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg th{background-color:#b9c9fe;border-color:#aabcfe;border-style:solid;border-width:1px;color:#039;
  font-family:Arial, sans-serif;font-size:14px;font-weight:normal;overflow:hidden;padding:10px 5px;word-break:normal;}
.tg .tg-qivn{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;vertical-align:top}
.tg .tg-s7u5{border-color:inherit;font-family:Impact, Charcoal, sans-serif !important;text-align:center;vertical-align:middle}
</style>"""

    header = """
<table class="tg">
<thead>
  <tr>
    <th class="tg-qivn">رطوبت</th>
    <th class="tg-qivn">بارش</th>
    <th class="tg-qivn">سرعت باد</th>
    <th class="tg-qivn" colspan="2">(&deg;C) دما</th>
    <th class="tg-s7u5" rowspan="2">تاریخ</th>
  </tr>
  <tr>
    <th class="tg-qivn">درصد</th>
    <th class="tg-qivn">میلی متر</th>
    <th class="tg-qivn">Km/h</th>
    <th class="tg-qivn">کمینه</th>
    <th class="tg-qivn"><span style="font-weight:400;font-style:normal">بیشینه</span><br></th>
  </tr>
</thead>
<tbody>"""

    ending = """
</tbody>
</table>
"""
    num_rows = len(days)

    row = """<tr>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
    <td class="tg-qivn">{}</td>
  </tr>"""

    rows = ""
    for i in range(num_rows):
        rows = rows + row.format(rh[i], rain[i], wind[i], tmin[i], tmax[i], days[i])

    html = style + header + rows + ending

    options = {"width": 450}
    from_string(html, output, options=options)
