#!/usr/bin/env python3
"""Fix YAML syntax errors in roju_ohariko.yaml.

Approach:
1. Fix structural indent issues (shifted entries, stray keys)
2. Quote ALL unquoted list items and unquoted scalar values that might
   contain YAML-special characters. Be aggressive but safe: if a value
   is a simple string/number/bool/null/date, leave it. Otherwise, quote it.
"""

import re
import shutil
import sys
import yaml

FILEPATH = "queue/inbox/roju_ohariko.yaml"

# Characters/patterns that make an unquoted YAML scalar problematic
YAML_SPECIAL_CHARS = set('{}[]|>&*!%@`')
# Patterns that indicate the value is safe unquoted
SAFE_VALUE_RE = re.compile(
    r'^('
    r'null|true|false|~'            # null/bool
    r'|"[^"]*"'                     # double-quoted
    r"|'[^']*'"                     # single-quoted
    r'|\d+(\.\d+)?'                 # number
    r'|\d{4}-\d{2}-\d{2}.*'        # date/timestamp
    r'|\[.*\]'                      # flow sequence (already bracketed)
    r'|\{.*\}'                      # flow mapping (already braced)
    r')$'
)


def get_indent(line):
    return len(line) - len(line.lstrip(' '))


def value_needs_quoting(val):
    """Conservative check: does this value need quoting?"""
    val = val.strip()
    if not val:
        return False
    # Already quoted
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return False
    # Block scalar indicator (standalone | or >)
    if val in ('|', '>', '|+', '|-', '>+', '>-', '|2', '>2'):
        return False
    # Flow collections that are complete
    if val.startswith('[') and val.endswith(']'):
        return False
    if val.startswith('{') and val.endswith('}'):
        return False
    # Check for special chars
    if any(c in val for c in YAML_SPECIAL_CHARS):
        return True
    # Colon followed by space in the value (would be parsed as mapping)
    # But this is in a list item context so less dangerous
    return False


def quote_value(value):
    """Wrap in double quotes, escaping internal quotes and backslashes."""
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return '"' + escaped + '"'


def fix_indent(lines):
    """Pass 1: Fix structural indent issues."""
    fixed = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            fixed.append(line)
            i += 1
            continue

        if stripped.startswith('#'):
            fixed.append(line)
            i += 1
            continue

        indent = get_indent(line)

        # Remove stray "audit_reports:" key
        if stripped == 'audit_reports:':
            i += 1
            continue

        # Entry at indent 0: needs +2
        if indent == 0 and stripped.startswith('- ') and \
           re.match(r'^- (subtask_id|audit_request|id):', stripped):
            fixed.append('  ' + line)
            i += 1
            while i < n:
                nline = lines[i]
                ns = nline.strip()
                ni = get_indent(nline)
                if not ns:
                    fixed.append(nline)
                    i += 1
                    continue
                if ns.startswith('#') and ni <= 2:
                    break
                if ni == 0 and not ns.startswith('#'):
                    break
                if re.match(r'^  - (subtask_id|audit_request|id):', nline):
                    break
                fixed.append('  ' + nline)
                i += 1
            continue

        # Entry at indent 4: needs -2
        if indent == 4 and re.match(r'^    - (subtask_id|audit_request|id):', line):
            fixed.append(line[2:])
            i += 1
            while i < n:
                nline = lines[i]
                ns = nline.strip()
                ni = get_indent(nline)
                if not ns:
                    fixed.append(nline)
                    i += 1
                    continue
                if re.match(r'^  - (subtask_id|audit_request|id):', nline):
                    break
                if re.match(r'^    - (subtask_id|audit_request|id):', nline):
                    break
                if ni == 0 and ns.startswith('- '):
                    break
                if ni == 0 and ns.startswith('#'):
                    break
                if ni <= 1 and not ns.startswith('#'):
                    break
                if re.match(r'^  #', nline):
                    break
                if ni >= 2:
                    fixed.append(nline[2:])
                else:
                    fixed.append(nline)
                i += 1
            continue

        # Over-indented entry keys at indent 6 -> 4
        ENTRY_KEYS = {
            'max_score', 'breakdown', 'summary', 'detail_ref', 'findings',
            'read', 'status', 'score', 'judgement', 'audit_result',
            'timestamp', 'kousatsu_registered', 'recommendation',
            'audited_at', 'karo_note', 'cmd_id', 'worker', 'project',
            'target_path', 'commit', 'description', 'files',
            'audit_points', 'requested_at', 'review_points',
            'design_doc', 'target_files', 'subtask_ids', 'commits'
        }
        BREAKDOWN_KEYS = {
            'completeness', 'accuracy', 'formatting', 'consistency',
            'cross_consistency'
        }

        if indent == 6:
            m = re.match(r'^\s+([a-z_]+)\s*:', line)
            if m and m.group(1) in ENTRY_KEYS:
                fixed.append(line[2:])
                i += 1
                continue

        if indent == 8:
            m = re.match(r'^\s+([a-z_]+)\s*:', line)
            if m and m.group(1) in BREAKDOWN_KEYS:
                fixed.append(line[2:])
                i += 1
                continue
            if stripped.startswith('- '):
                for j in range(len(fixed) - 1, max(len(fixed) - 20, -1), -1):
                    pline = fixed[j].strip()
                    if not pline or pline.startswith('- '):
                        continue
                    if pline == 'findings:':
                        fixed.append(line[2:])
                        break
                    else:
                        fixed.append(line)
                        break
                else:
                    fixed.append(line)
                i += 1
                continue

        fixed.append(line)
        i += 1

    return fixed


def fix_quoting(lines):
    """Pass 2: Quote unquoted values containing special chars."""
    fixed = []
    in_block_scalar = False
    block_scalar_indent = 0

    for line in lines:
        stripped = line.strip()
        indent = get_indent(line)

        # Track block scalars (summary: | etc)
        if in_block_scalar:
            if stripped and indent <= block_scalar_indent:
                in_block_scalar = False
            else:
                fixed.append(line)
                continue

        if not stripped or stripped.startswith('#'):
            fixed.append(line)
            continue

        # Detect block scalar start: "key: |" or "key: >"
        m = re.match(r'^(\s*[a-z_]+:\s+)(\||\>)(\+|\-|\d+)?\s*$', line)
        if m:
            in_block_scalar = True
            block_scalar_indent = indent
            fixed.append(line)
            continue

        # List items: "  - value"
        m = re.match(r'^(\s+- )(.+)$', line.rstrip('\n'))
        if m:
            prefix = m.group(1)
            value = m.group(2)
            if value_needs_quoting(value):
                fixed.append(prefix + quote_value(value) + '\n')
                continue

        # Mapping values: "key: value"
        m = re.match(r'^(\s+[a-z_]+:\s+)(.+)$', line.rstrip('\n'))
        if m:
            prefix = m.group(1)
            value = m.group(2)
            if value_needs_quoting(value):
                fixed.append(prefix + quote_value(value) + '\n')
                continue

        fixed.append(line)

    return fixed


def main():
    with open(FILEPATH, 'r') as f:
        original_lines = f.readlines()

    shutil.copy2(FILEPATH, FILEPATH + '.bak')

    print(f"Original: {len(original_lines)} lines")

    lines = fix_indent(original_lines)
    print(f"After indent fix: {len(lines)} lines")

    lines = fix_quoting(lines)
    print(f"After quoting fix: {len(lines)} lines")

    with open(FILEPATH, 'w') as f:
        f.writelines(lines)

    # Iterative fix for remaining issues
    for attempt in range(20):
        try:
            with open(FILEPATH, 'r') as f:
                data = yaml.safe_load(f)
            if data and 'audit_queue' in data:
                print(f"YAML valid! audit_queue has {len(data['audit_queue'])} entries")
                return True
            else:
                keys = list(data.keys()) if data else 'empty'
                print(f"YAML valid but unexpected structure: {keys}")
                return True
        except yaml.YAMLError as e:
            if not hasattr(e, 'problem_mark') or not e.problem_mark:
                print(f"YAML error without line info: {e}")
                return False

            err_line = e.problem_mark.line  # 0-indexed
            err_col = e.problem_mark.column
            print(f"Attempt {attempt + 1}: Error at line {err_line + 1}, col {err_col + 1}: {e.problem}")

            with open(FILEPATH, 'r') as f:
                all_lines = f.readlines()

            if err_line >= len(all_lines):
                print("Error line out of range")
                return False

            problem_line = all_lines[err_line]
            pstripped = problem_line.strip()
            pindent = get_indent(problem_line)

            fixed = False

            # Try quoting the list item
            m = re.match(r'^(\s+- )(.+)$', problem_line.rstrip('\n'))
            if m and not (m.group(2).startswith('"') and m.group(2).rstrip().endswith('"')):
                all_lines[err_line] = m.group(1) + quote_value(m.group(2)) + '\n'
                fixed = True

            # Try quoting the mapping value
            if not fixed:
                m = re.match(r'^(\s+[a-z_]+:\s+)(.+)$', problem_line.rstrip('\n'))
                if m and not (m.group(2).startswith('"') and m.group(2).rstrip().endswith('"')):
                    all_lines[err_line] = m.group(1) + quote_value(m.group(2)) + '\n'
                    fixed = True

            # Also check if previous line is the actual problem
            if not fixed and err_line > 0:
                prev_line = all_lines[err_line - 1]
                m = re.match(r'^(\s+- )(.+)$', prev_line.rstrip('\n'))
                if m and not (m.group(2).startswith('"') and m.group(2).rstrip().endswith('"')):
                    all_lines[err_line - 1] = m.group(1) + quote_value(m.group(2)) + '\n'
                    fixed = True

            if not fixed:
                m = re.match(r'^(\s+[a-z_]+:\s+)(.+)$', all_lines[err_line - 1].rstrip('\n') if err_line > 0 else '')
                if m and not (m.group(2).startswith('"') and m.group(2).rstrip().endswith('"')):
                    all_lines[err_line - 1] = m.group(1) + quote_value(m.group(2)) + '\n'
                    fixed = True

            if fixed:
                with open(FILEPATH, 'w') as f:
                    f.writelines(all_lines)
            else:
                print(f"Could not auto-fix line {err_line + 1}: {problem_line.rstrip()}")
                return False

    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
