"""Opt-in real Docker boundary check, executed by the hosted container CI job."""
import os
import textwrap

import pytest

from siteforge.sandbox import DockerSandbox


@pytest.mark.skipif(not os.environ.get('SITEFORGE_TEST_DOCKER_IMAGE'), reason='requires real Docker engine and reviewed digest')
def test_actual_container_has_no_network_host_writes_credentials_or_privileges(tmp_path, monkeypatch):
    job=tmp_path/'job'
    tests=job/'tests'
    tests.mkdir(parents=True)
    (tests/'test_boundary.py').write_text(textwrap.dedent('''
        import os
        import socket
        import unittest
        from pathlib import Path

        class Boundary(unittest.TestCase):
            def test_nonroot_and_no_credentials(self):
                self.assertEqual(os.getuid(),65534)
                self.assertNotIn('SITEFORGE_FAKE_HOST_SECRET',os.environ)
                status=Path('/proc/self/status').read_text()
                capabilities=next(line.split()[1] for line in status.splitlines() if line.startswith('CapEff:'))
                self.assertEqual(int(capabilities,16),0)

            def test_host_mount_and_root_are_read_only(self):
                for name in ['/workspace/escape.txt','/escape.txt']:
                    with self.assertRaises(OSError):
                        Path(name).write_text('must fail')
                self.assertFalse(Path('/private-host-marker.txt').exists())

            def test_external_network_is_unavailable(self):
                with self.assertRaises(OSError):
                    socket.create_connection(('1.1.1.1',443),timeout=.5)
    '''),encoding='utf-8')
    monkeypatch.setenv('SITEFORGE_FAKE_HOST_SECRET','fixture-credential-never-forwarded')
    runner=DockerSandbox(tmp_path,os.environ['SITEFORGE_TEST_DOCKER_IMAGE'])
    result=runner.run(job,'python_unittest',timeout_seconds=60)
    assert result.returncode==0, result.output
    assert not (job/'escape.txt').exists()
    assert result.network=='none'
    assert not result.output_truncated
