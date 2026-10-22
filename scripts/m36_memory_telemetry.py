"""Read-only Linux memory diagnostics; missing host evidence stays unavailable."""
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import platform
import re


def parse_kib_fields(raw):
    fields = {}
    for line in raw.splitlines():
        name, sep, value = line.partition(':')
        if not sep or name not in {'VmRSS', 'VmHWM', 'RssAnon', 'RssFile', 'RssShmem',
                                  'Rss', 'Pss', 'Private_Clean', 'Private_Dirty', 'Swap'}:
            continue
        number, unit = value.split()
        if unit != 'kB' or int(number) < 0:
            raise ValueError('expected nonnegative Linux KiB field')
        fields[name] = int(number)*1024
    return fields


def resolve_cgroups(membership, mountinfo):
    """Map process membership through mount roots, including escaped mount paths."""
    groups = []
    for entry in membership.splitlines():
        _, controllers, member = entry.split(':', 2)
        for line in mountinfo.splitlines():
            before, after = line.split(' - ', 1)
            columns, fs = before.split(), after.split()
            version = 2 if fs[0] == 'cgroup2' and controllers == '' else 1
            if version == 1 and not (fs[0] == 'cgroup' and 'memory' in controllers.split(',')
                                     and 'memory' in fs[2].split(',')):
                continue
            decode = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
            mount_root, mountpoint = map(decode, columns[3:5])
            try:
                relative = PurePosixPath(member).relative_to(mount_root)
            except ValueError:
                continue
            groups.append({'version': version,
                           'path': str(PurePosixPath(mountpoint)/relative), 'membership': member})
    return groups


def read_cgroup(root, version):
    names = ({'current_bytes': 'memory.current', 'peak_bytes': 'memory.peak',
              'limit_bytes': 'memory.max', 'events': 'memory.events'} if version == 2 else
             {'current_bytes': 'memory.usage_in_bytes', 'peak_bytes': 'memory.max_usage_in_bytes',
              'limit_bytes': 'memory.limit_in_bytes', 'events': 'memory.oom_control'})
    result = {'raw': {}, 'errors': {}}
    for field, name in names.items():
        try:
            raw = (Path(root)/name).read_text().strip()
            result['raw'][name] = raw
            result[field] = ({key: int(value) for key, value in
                              (line.split() for line in raw.splitlines())} if field == 'events'
                             else None if raw == 'max' else int(raw))
        except (OSError, ValueError) as exc:
            result[field] = None
            result['errors'][name] = str(exc)
    return result


def assess_memory(process, cgroups, configured_limit_bytes):
    peaks = [process.get(key) for key in ('ru_maxrss_bytes', 'vmhwm_bytes')]
    peaks = [value for value in peaks if value is not None]
    matching = [group for group in cgroups if group.get('limit_bytes') == configured_limit_bytes
                and group.get('peak_bytes') is not None and group.get('events') is not None]
    failed = any(group['peak_bytes'] > configured_limit_bytes or group['peak_bytes'] < 0 or
                 any(group['events'].get(key, 0) > 0 for key in ('oom', 'oom_kill', 'under_oom'))
                 for group in matching)
    return {'configured_limit_bytes': configured_limit_bytes,
            'process_high_water_verdict': ('UNAVAILABLE' if not peaks else
                                           'PASS' if max(peaks) <= configured_limit_bytes else 'FAIL'),
            'container_peak_verdict': ('FAIL' if failed else 'PASS_REPORTED_CGROUP_PEAK' if matching
                                       else 'UNAVAILABLE'),
            'reported_container_peak_verified': bool(matching) and not failed,
            'physical_container_peak_verified': False,
            'scope': 'In-container process/cgroup interfaces; no independent host/provider metric. '
                     'Current samples are not peaks; process RSS is not container usage.'}


def snapshot(stage, configured_limit_bytes=5*2**30):
    import resource
    raw, errors = {}, {}
    for name in ('status', 'smaps_rollup', 'cgroup', 'mountinfo'):
        try:
            raw[name] = (Path('/proc/self')/name).read_text()
        except OSError as exc:
            errors[name] = str(exc)
    status = parse_kib_fields(raw.get('status', ''))
    process = {'ru_maxrss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
               'vmhwm_bytes': status.get('VmHWM'), 'vmrss_bytes': status.get('VmRSS'),
               'status_bytes': status, 'smaps_rollup_bytes': parse_kib_fields(raw.get('smaps_rollup', ''))}
    groups = [{**entry, **read_cgroup(entry['path'], entry['version'])}
              for entry in resolve_cgroups(raw.get('cgroup', ''), raw.get('mountinfo', ''))]
    # Preserve only memory-controller mounts, not unrelated mount paths.
    raw['mountinfo'] = '\n'.join(line for line in raw.get('mountinfo', '').splitlines()
                                 if ' - cgroup' in line)
    return {'stage': stage, 'pid': os.getpid(), 'checked_utc': datetime.now(timezone.utc).isoformat(),
            'kernel': platform.release(), 'kernel_version': platform.version(),
            'process': process, 'cgroups': groups, 'raw_proc': raw, 'errors': errors,
            'assessment': assess_memory(process, groups, configured_limit_bytes)}
