#!/usr/bin/env python3
"""
test_auto_unblock.py - Tests for blocked_by + auto_unblock functionality.

Tests:
1. Single dependency: A -> B (B blocked by A, complete A -> B unblocks)
2. Multiple dependencies: A,B -> C (C blocked by A+B, both must complete)
3. Chain dependency: A -> B -> C (complete A -> B unblocks, complete B -> C unblocks)
4. Cycle detection: A -> B -> A (should error)
5. Worker with assignment: auto_unblock sets status=assigned when worker is set
6. Worker without assignment: auto_unblock sets status=pending when no worker
7. Partial dependency: A,B -> C, only A done -> C stays blocked
8. Non-existent dependency: should error on add
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
BOTSUNICHIROKU = SCRIPT_DIR / "botsunichiroku.py"

# Use temp DB for testing
TEST_DIR = tempfile.mkdtemp()
TEST_DB = os.path.join(TEST_DIR, "test_botsunichiroku.db")


def setup_test_db():
    """Create a fresh test database."""
    conn = sqlite3.connect(TEST_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            command TEXT NOT NULL,
            project TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            assigned_karo TEXT,
            details TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subtasks (
            id TEXT PRIMARY KEY,
            parent_cmd TEXT NOT NULL,
            worker_id TEXT,
            project TEXT,
            description TEXT NOT NULL,
            target_path TEXT,
            status TEXT DEFAULT 'pending',
            wave INTEGER DEFAULT 1,
            notes TEXT,
            needs_audit INTEGER DEFAULT 0,
            audit_status TEXT DEFAULT NULL,
            blocked_by TEXT,
            assigned_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (parent_cmd) REFERENCES commands(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT,
            completed_steps TEXT,
            blocking_reason TEXT,
            findings TEXT,
            next_actions TEXT,
            files_modified TEXT,
            notes TEXT,
            skill_candidate_name TEXT,
            skill_candidate_desc TEXT,
            FOREIGN KEY (task_id) REFERENCES subtasks(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            display_name TEXT,
            model TEXT,
            status TEXT DEFAULT 'idle',
            current_task_id TEXT,
            pane_target TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Seed
    conn.execute("INSERT INTO commands VALUES ('cmd_test', '2026-01-01', 'test cmd', 'test', 'medium', 'in_progress', 'roju', NULL, '2026-01-01', NULL)")
    conn.execute("INSERT OR IGNORE INTO counters VALUES ('cmd_id', 999)")
    conn.execute("INSERT OR IGNORE INTO counters VALUES ('subtask_id', 999)")

    conn.commit()
    conn.close()


def run_cli(*args):
    """Run botsunichiroku.py with custom DB path."""
    env = os.environ.copy()
    cmd = [sys.executable, str(BOTSUNICHIROKU)] + list(args)
    # We need to monkey-patch the DB path. Simplest: use subprocess and override
    # Actually, let's use a different approach: copy script and modify DB path
    # Simpler: just use the real DB path mechanism via env/symlink
    # Easiest: symlink the test db to the expected path temporarily

    # Actually, let's just run it directly and capture output
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result


def run_cli_with_test_db(*args):
    """Run CLI commands but use test DB by patching."""
    conn = sqlite3.connect(TEST_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


class TestAutoUnblock:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def assert_eq(self, actual, expected, msg):
        if actual == expected:
            self.passed += 1
            print(f"  ✅ {msg}")
        else:
            self.failed += 1
            self.errors.append(f"{msg}: expected={expected}, actual={actual}")
            print(f"  ❌ {msg}: expected={expected}, actual={actual}")

    def test_1_single_dependency(self):
        """A -> B: complete A unblocks B"""
        print("\n=== Test 1: Single dependency ===")
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        # Create subtask A (no dependency)
        conn.execute("INSERT INTO subtasks VALUES ('st_001', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        # Create subtask B (blocked by A)
        conn.execute("INSERT INTO subtasks VALUES ('st_002', 'cmd_test', 'ashigaru2', 'test', 'Task B', NULL, 'blocked', 2, NULL, 0, NULL, 'st_001', NULL, NULL)")
        conn.commit()

        # Import auto_unblock
        sys.path.insert(0, str(SCRIPT_DIR))
        from botsunichiroku import auto_unblock

        # Complete A
        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_001'")
        unblocked = auto_unblock(conn, 'st_001')
        conn.commit()

        # Check B is now assigned
        row = conn.execute("SELECT status FROM subtasks WHERE id = 'st_002'").fetchone()
        self.assert_eq(row['status'], 'assigned', "B should be assigned after A completes")
        self.assert_eq(len(unblocked), 1, "One subtask should be unblocked")

        conn.close()

    def test_2_multiple_dependencies(self):
        """A, B -> C: both A and B must complete to unblock C"""
        print("\n=== Test 2: Multiple dependencies ===")
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        conn.execute("INSERT INTO subtasks VALUES ('st_010', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_011', 'cmd_test', 'ashigaru2', 'test', 'Task B', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_012', 'cmd_test', 'ashigaru3', 'test', 'Task C', NULL, 'blocked', 2, NULL, 0, NULL, 'st_010,st_011', NULL, NULL)")
        conn.commit()

        from botsunichiroku import auto_unblock

        # Complete only A
        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_010'")
        unblocked = auto_unblock(conn, 'st_010')
        conn.commit()

        row = conn.execute("SELECT status FROM subtasks WHERE id = 'st_012'").fetchone()
        self.assert_eq(row['status'], 'blocked', "C should still be blocked (B not done)")
        self.assert_eq(len(unblocked), 0, "No subtasks should be unblocked yet")

        # Complete B
        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_011'")
        unblocked = auto_unblock(conn, 'st_011')
        conn.commit()

        row = conn.execute("SELECT status FROM subtasks WHERE id = 'st_012'").fetchone()
        self.assert_eq(row['status'], 'assigned', "C should be assigned after both A,B complete")
        self.assert_eq(len(unblocked), 1, "One subtask should be unblocked")

        conn.close()

    def test_3_chain_dependency(self):
        """A -> B -> C: chain unblock"""
        print("\n=== Test 3: Chain dependency ===")
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        conn.execute("INSERT INTO subtasks VALUES ('st_020', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_021', 'cmd_test', 'ashigaru2', 'test', 'Task B', NULL, 'blocked', 2, NULL, 0, NULL, 'st_020', NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_022', 'cmd_test', 'ashigaru3', 'test', 'Task C', NULL, 'blocked', 3, NULL, 0, NULL, 'st_021', NULL, NULL)")
        conn.commit()

        from botsunichiroku import auto_unblock

        # Complete A -> B should unblock, C should remain blocked
        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_020'")
        unblocked = auto_unblock(conn, 'st_020')
        conn.commit()

        row_b = conn.execute("SELECT status FROM subtasks WHERE id = 'st_021'").fetchone()
        row_c = conn.execute("SELECT status FROM subtasks WHERE id = 'st_022'").fetchone()
        self.assert_eq(row_b['status'], 'assigned', "B should be assigned after A completes")
        self.assert_eq(row_c['status'], 'blocked', "C should still be blocked (B not done)")

        # Complete B -> C should unblock
        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_021'")
        unblocked = auto_unblock(conn, 'st_021')
        conn.commit()

        row_c = conn.execute("SELECT status FROM subtasks WHERE id = 'st_022'").fetchone()
        self.assert_eq(row_c['status'], 'assigned', "C should be assigned after B completes")

        conn.close()

    def test_4_cycle_detection(self):
        """Cycle detection via CLI --blocked-by update"""
        print("\n=== Test 4: Cycle detection ===")
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        conn.execute("INSERT INTO subtasks VALUES ('st_030', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'blocked', 1, NULL, 0, NULL, 'st_031', NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_031', 'cmd_test', 'ashigaru2', 'test', 'Task B', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.commit()

        from botsunichiroku import _detect_cycle

        # Try to create cycle: B blocked by A (A is already blocked by B)
        cycle = _detect_cycle(conn, 'st_031', ['st_030'])
        self.assert_eq(cycle is not None, True, "Cycle should be detected (A->B->A)")

        conn.close()

    def test_5_worker_with_assignment(self):
        """Auto-unblock sets status=assigned when worker is set"""
        print("\n=== Test 5: Worker with assignment ===")
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        conn.execute("INSERT INTO subtasks VALUES ('st_040', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_041', 'cmd_test', 'ashigaru2', 'test', 'Task B', NULL, 'blocked', 2, NULL, 0, NULL, 'st_040', NULL, NULL)")
        conn.commit()

        from botsunichiroku import auto_unblock

        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_040'")
        unblocked = auto_unblock(conn, 'st_040')
        conn.commit()

        row = conn.execute("SELECT status FROM subtasks WHERE id = 'st_041'").fetchone()
        self.assert_eq(row['status'], 'assigned', "Should be 'assigned' (worker is set)")
        self.assert_eq('ashigaru2' in unblocked[0], True, "Should mention worker in output")

        conn.close()

    def test_6_worker_without_assignment(self):
        """Auto-unblock sets status=pending when no worker"""
        print("\n=== Test 6: Worker without assignment ===")
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        conn.execute("INSERT INTO subtasks VALUES ('st_050', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'assigned', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_051', 'cmd_test', NULL, 'test', 'Task B', NULL, 'blocked', 2, NULL, 0, NULL, 'st_050', NULL, NULL)")
        conn.commit()

        from botsunichiroku import auto_unblock

        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_050'")
        unblocked = auto_unblock(conn, 'st_050')
        conn.commit()

        row = conn.execute("SELECT status FROM subtasks WHERE id = 'st_051'").fetchone()
        self.assert_eq(row['status'], 'pending', "Should be 'pending' (no worker)")

        conn.close()

    def test_7_partial_dependency(self):
        """A,B -> C: only A done, C stays blocked"""
        print("\n=== Test 7: Partial dependency ===")
        # Already covered in test 2 first half, but explicit
        conn = sqlite3.connect(TEST_DB)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        conn.execute("INSERT INTO subtasks VALUES ('st_060', 'cmd_test', 'ashigaru1', 'test', 'Task A', NULL, 'in_progress', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_061', 'cmd_test', 'ashigaru2', 'test', 'Task B', NULL, 'in_progress', 1, NULL, 0, NULL, NULL, NULL, NULL)")
        conn.execute("INSERT INTO subtasks VALUES ('st_062', 'cmd_test', 'ashigaru3', 'test', 'Task C', NULL, 'blocked', 2, NULL, 0, NULL, 'st_060,st_061', NULL, NULL)")
        conn.commit()

        from botsunichiroku import auto_unblock

        conn.execute("UPDATE subtasks SET status = 'done' WHERE id = 'st_060'")
        unblocked = auto_unblock(conn, 'st_060')
        conn.commit()

        row = conn.execute("SELECT status FROM subtasks WHERE id = 'st_062'").fetchone()
        self.assert_eq(row['status'], 'blocked', "C stays blocked (B still in_progress)")
        self.assert_eq(len(unblocked), 0, "No subtasks unblocked")

        conn.close()

    def test_8_nonexistent_dependency(self):
        """Non-existent dependency should error"""
        print("\n=== Test 8: Non-existent dependency ===")
        # This is tested via CLI, let's test the CLI directly
        result = subprocess.run(
            [sys.executable, str(BOTSUNICHIROKU), "subtask", "add", "cmd_test",
             "test task", "--blocked-by", "st_nonexistent"],
            capture_output=True, text=True
        )
        self.assert_eq(result.returncode != 0, True, "Should error for non-existent dependency")
        self.assert_eq("not found" in result.stderr, True, "Error message should mention 'not found'")

    def summary(self):
        print(f"\n{'='*60}")
        print(f"  Results: {self.passed} passed, {self.failed} failed")
        print(f"{'='*60}")
        if self.errors:
            print("\n  Failures:")
            for e in self.errors:
                print(f"    - {e}")
        return self.failed == 0


def main():
    setup_test_db()

    # Monkey-patch the DB_PATH in botsunichiroku module
    sys.path.insert(0, str(SCRIPT_DIR))
    import botsunichiroku
    botsunichiroku.DB_PATH = Path(TEST_DB)

    tests = TestAutoUnblock()
    tests.test_1_single_dependency()
    tests.test_2_multiple_dependencies()
    tests.test_3_chain_dependency()
    tests.test_4_cycle_detection()
    tests.test_5_worker_with_assignment()
    tests.test_6_worker_without_assignment()
    tests.test_7_partial_dependency()
    tests.test_8_nonexistent_dependency()

    success = tests.summary()

    # Cleanup
    import shutil
    shutil.rmtree(TEST_DIR, ignore_errors=True)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
