"""MCP package provenance positive and negative controls; zero build/network."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import verify_mcp_tool_metadata as target

HEAD = "a" * 40


def synthetic(repo=target.REPO, commit=HEAD, project=target.REPO,
              desc=target.DESCRIPTION, license="MIT", package_type="DotnetTool",
              missing=None):
    xml = f"""<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
<metadata><id>{target.PACKAGE}</id><version>{target.VERSION}</version>
<description>{desc}</description><projectUrl>{project}</projectUrl>
<license type="expression">{license}</license>
<repository type="git" url="{repo}" commit="{commit}"/>
<packageTypes><packageType name="{package_type}"/></packageTypes>
</metadata></package>"""
    stream = BytesIO()
    with ZipFile(stream, "w") as z:
        z.writestr(target.PACKAGE + ".nuspec", xml)
        for f in target.FILES:
            if f != missing:
                z.writestr(f, b"owned-fixture")
    return stream.getvalue()


class NugetToolContract(unittest.TestCase):
    def check(self, mutated=None, pattern=None):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / (target.PACKAGE + "." + target.VERSION + ".nupkg")
            f.write_bytes(synthetic(**(mutated or {})))
            if pattern is None:
                self.assertEqual(target.verify(f, HEAD)["status"],
                                 "mcp_tool_provenance_verified")
            else:
                with self.assertRaisesRegex(ValueError, pattern):
                    target.verify(f, HEAD)

    def test_positive(self):
        self.check()

    def test_old_organization_is_rejected(self):
        self.check({"repo": "https://github.com/AlexanderLevenskikh/selenium-playwright-migrator-mcp"}, "repository URL/commit")

    def test_pr_merge_sha_is_not_declared_source_head(self):
        self.check({"commit": "cb4b9686f998d1f7ed37bea36a2bfd55e5af78b2"}, "repository URL/commit")

    def test_placeholder_description(self):
        self.check({"desc": "Package Description"}, "description")

    def test_wrong_project_url(self):
        self.check({"project": "https://github.com/old/target"}, "project URL")

    def test_unlicensed(self):
        self.check({"license": "GPL-3.0"}, "MIT")

    def test_not_dotnet_tool(self):
        self.check({"package_type": "Dependency"}, "DotnetTool")

    def test_missing_executable_or_notices(self):
        for item in target.FILES:
            with self.subTest(item=item):
                self.check({"missing": item}, "tool/notice")

    def test_invalid_expected_sha(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / (target.PACKAGE + "." + target.VERSION + ".nupkg")
            f.write_bytes(synthetic())
            with self.assertRaisesRegex(ValueError, "SHA40"):
                target.verify(f, "wrong")


if __name__ == "__main__":
    unittest.main()
