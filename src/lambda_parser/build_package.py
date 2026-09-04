"""
AWS Lambda Build & Packaging Script
Author: Gauransh (23/IT/057)

Packages AWS Lambda 1 (Parser) along with its third-party dependency 'PyPDF2' into a deployment zip file ready for AWS Lambda upload.
"""

import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

BUILD_DIR = os.path.join(SCRIPT_DIR, "build_pkg")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
ZIP_NAME = "lambda_parser_deployment"


def build():
    print("[BUILD] Packaging AWS Lambda 1 Deployment Package (with PyPDF2)...")

    # Clean prior build directories
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    # Copy handler file to build directory
    handler_source = os.path.join(SCRIPT_DIR, "lambda_function.py")
    shutil.copy(handler_source, BUILD_DIR)
    print("  [OK] Copied handler script.")

    # Install PyPDF2 into build directory
    print("  [OK] Downloading and vendoring PyPDF2 into build package...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "PyPDF2",
        "-t", BUILD_DIR,
        "--quiet"
    ])

    # Zip the build directory
    output_zip_path = os.path.join(DIST_DIR, ZIP_NAME)
    archive_format = "zip"
    shutil.make_archive(output_zip_path, archive_format, BUILD_DIR)

    # Cleanup temporary build folder
    shutil.rmtree(BUILD_DIR)

    final_zip = f"{output_zip_path}.zip"
    file_size_kb = os.path.getsize(final_zip) / 1024.0
    print(f"[SUCCESS] Deployment zip successfully created at:\n   {final_zip} ({file_size_kb:.2f} KB)")


if __name__ == "__main__":
    build()
