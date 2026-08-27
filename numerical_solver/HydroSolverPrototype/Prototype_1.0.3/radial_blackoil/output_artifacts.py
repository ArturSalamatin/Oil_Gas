from pathlib import Path
import math

from .units import DAY_TO_S


def _format_report_time(td):
    total_s = int(round(float(td) * DAY_TO_S))
    if total_s == 0:
        return '0 d'
    days, rem = divmod(total_s, int(DAY_TO_S))
    if rem == 0:
        return f'{days} d'
    if days > 0 and rem < 3600:
        return f'{days} d + {rem} s'
    if days > 0:
        hh, rem = divmod(rem, 3600)
        mm, ss = divmod(rem, 60)
        tail = []
        if hh:
            tail.append(f'{hh} h')
        if mm:
            tail.append(f'{mm} min')
        if ss:
            tail.append(f'{ss} s')
        return f'{days} d + ' + ' '.join(tail)
    if total_s % 3600 == 0:
        return f'{total_s // 3600} h'
    if total_s % 60 == 0:
        return f'{total_s // 60} min'
    return f'{total_s} s'


def _xlsx_value(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return 'nan' if math.isnan(value) else ('inf' if value > 0 else '-inf')
        return value
    return value


def write_results_xlsx(out, grid, hist):
    """Write an engineer-friendly Excel mirror of rates/profiles/material balance."""
    import xlsxwriter

    out = Path(out)
    path = out / 'results.xlsx'
    workbook = xlsxwriter.Workbook(path)
    header_fmt = workbook.add_format({
        'bold': True,
        'font_color': 'white',
        'bg_color': '#1F4E78',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
    })
    num_fmt = workbook.add_format({'num_format': '0.000000'})
    sci_fmt = workbook.add_format({'num_format': '0.000000E+00'})

    # rates
    ws = workbook.add_worksheet('rates')
    rate_headers = ['time_day','oil_rate_sm3_day','gas_rate_sm3_day','GOR_sm3_sm3','BHP_bar','control_mode','constraint_active']
    for col, h in enumerate(rate_headers):
        ws.write(0, col, h, header_fmt)
    for row, (td, r, bhp) in enumerate(hist.report_rates, start=1):
        values = [
            td,
            r['oil_sm3_s'] * DAY_TO_S,
            r['total_gas_sm3_s'] * DAY_TO_S,
            r['gor_sm3_sm3'],
            bhp,
            r.get('control_mode'),
            r.get('constraint_active'),
        ]
        for col, v in enumerate(values):
            v = _xlsx_value(v)
            if isinstance(v, bool):
                ws.write_boolean(row, col, v)
            elif isinstance(v, (int, float)):
                ws.write_number(row, col, v, num_fmt)
            else:
                ws.write(row, col, v)
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(1, len(hist.report_rates)), len(rate_headers)-1)
    ws.set_column(0, 4, 20)
    ws.set_column(5, 6, 18)

    # profiles
    ws = workbook.add_worksheet('profiles')
    profile_headers = ['time_day','cell','radius_m','pressure_bar','Sg','Rs']
    for col, h in enumerate(profile_headers):
        ws.write(0, col, h, header_fmt)
    row = 1
    for td, s in hist.report_states:
        for i in range(grid.n):
            values = [td, i+1, grid.centers_m[i], s.pressure_bar[i], s.sg[i], s.rs_sm3_sm3[i]]
            for col, v in enumerate(values):
                if col == 1:
                    ws.write_number(row, col, int(v))
                else:
                    ws.write_number(row, col, float(v), num_fmt)
            row += 1
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(1, row-1), len(profile_headers)-1)
    ws.set_column(0, 5, 20)

    # material balance
    ws = workbook.add_worksheet('material_balance')
    mb_headers = [
        'time_day','oil_initial_sm3','oil_current_sm3','oil_produced_well_sm3','oil_outer_net_out_sm3',
        'oil_balance_error_sm3','oil_balance_error_pct_initial','gas_initial_sm3','gas_current_total_sm3',
        'gas_current_dissolved_sm3','gas_current_free_sm3','gas_produced_well_sm3','gas_outer_net_out_sm3',
        'gas_balance_error_sm3','gas_balance_error_pct_initial'
    ]
    for col, h in enumerate(mb_headers):
        ws.write(0, col, h, header_fmt)
    for row, rec in enumerate(hist.material_balance, start=1):
        for col, h in enumerate(mb_headers):
            v = _xlsx_value(rec.get(h))
            if isinstance(v, (int, float)):
                fmt = sci_fmt if 'error' in h else num_fmt
                ws.write_number(row, col, v, fmt)
            else:
                ws.write(row, col, v)
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(1, len(hist.material_balance)), len(mb_headers)-1)
    ws.set_column(0, 14, 24)

    workbook.close()
    return path


def _save_rate_plot(out, hist, key, ylabel, filename):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    times = [float(td) for td, _, _ in hist.report_rates]
    if key == 'oil':
        vals = [r['oil_sm3_s'] * DAY_TO_S for _, r, _ in hist.report_rates]
    elif key == 'gas':
        vals = [r['total_gas_sm3_s'] * DAY_TO_S for _, r, _ in hist.report_rates]
    elif key == 'gor':
        vals = [r['gor_sm3_sm3'] for _, r, _ in hist.report_rates]
    elif key == 'bhp':
        vals = [bhp for _, _, bhp in hist.report_rates]
    else:
        raise ValueError(key)

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(times, vals, marker='o', linewidth=1.4, markersize=3.5)
    ax.set_xlabel('Time, day')
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(Path(out) / filename, dpi=180)
    plt.close(fig)


def _save_profile_plot(out, grid, hist, field, ylabel, filename):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(13.5, 8.0))
    for td, s in hist.report_states:
        if field == 'pressure':
            y = s.pressure_bar
        elif field == 'sg':
            y = s.sg
        elif field == 'rs':
            y = s.rs_sm3_sm3
        else:
            raise ValueError(field)
        ax.plot(grid.centers_m, y, linewidth=1.2, label=_format_report_time(td))

    ax.set_xscale('log')
    ax.set_xlabel('Radius, m')
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    n = max(1, len(hist.report_states))
    legend_cols = 2 if n > 14 else 1
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=7.0, ncol=legend_cols, borderaxespad=0.0)
    fig.tight_layout(rect=(0.0, 0.0, 0.79 if legend_cols == 1 else 0.68, 1.0))
    fig.savefig(Path(out) / filename, dpi=180)
    plt.close(fig)


def write_png_plots(out, grid, hist):
    """Write one PNG per rate/profile variable using all SCHEDULE report times."""
    if hist.report_rates:
        _save_rate_plot(out, hist, 'oil', 'Oil rate, Sm3/day', 'oil_rate.png')
        _save_rate_plot(out, hist, 'gas', 'Gas rate, Sm3/day', 'gas_rate.png')
        _save_rate_plot(out, hist, 'gor', 'GOR, Sm3/Sm3', 'GOR.png')
        _save_rate_plot(out, hist, 'bhp', 'BHP, bar(a)', 'BHP.png')
    if hist.report_states:
        _save_profile_plot(out, grid, hist, 'pressure', 'Pressure, bar(a)', 'pressure_profiles.png')
        _save_profile_plot(out, grid, hist, 'sg', 'Gas saturation Sg', 'Sg_profiles.png')
        _save_profile_plot(out, grid, hist, 'rs', 'Rs, Sm3/Sm3', 'Rs_profiles.png')


def write_additional_outputs(out, grid, hist):
    write_results_xlsx(out, grid, hist)
    write_png_plots(out, grid, hist)
