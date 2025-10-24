#!/usr/bin/env python3
"""
Test runner script for Shitpost Alpha tests.
Provides convenient commands for running different test suites.
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"❌ {description} failed with error: {e}")
        return False


def run_unit_tests():
    """Run unit tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/shit/",
        "-v",
        "--tb=short",
        "-m", "unit"
    ]
    return run_command(cmd, "Unit Tests")


def run_integration_tests():
    """Run integration tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/integration/",
        "-v",
        "--tb=short",
        "-m", "integration"
    ]
    return run_command(cmd, "Integration Tests")


def run_e2e_tests():
    """Run end-to-end tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/integration/",
        "-v",
        "--tb=short",
        "-m", "e2e"
    ]
    return run_command(cmd, "End-to-End Tests")


def run_all_tests():
    """Run all tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "All Tests")


def run_tests_with_coverage():
    """Run tests with coverage reporting."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/",
        "--cov=shit",
        "--cov=shitvault",
        "--cov=shitposts",
        "--cov=shitpost_ai",
        "--cov-report=html",
        "--cov-report=term-missing",
        "-v"
    ]
    return run_command(cmd, "Tests with Coverage")


def run_specific_test(test_path):
    """Run a specific test file."""
    cmd = [
        sys.executable, "-m", "pytest",
        test_path,
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, f"Specific Test: {test_path}")


def run_parallel_tests():
    """Run tests in parallel."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/",
        "-n", "auto",
        "-v",
        "--tb=short"
    ]
    return run_command(cmd, "Parallel Tests")


def run_slow_tests():
    """Run slow tests."""
    cmd = [
        sys.executable, "-m", "pytest",
        "shit_tests/",
        "-v",
        "--tb=short",
        "-m", "slow"
    ]
    return run_command(cmd, "Slow Tests")


def install_test_dependencies():
    """Install test dependencies."""
    cmd = [
        sys.executable, "-m", "pip",
        "install",
        "-r", "shit_tests/requirements-test.txt"
    ]
    return run_command(cmd, "Install Test Dependencies")


def lint_tests():
    """Lint test files."""
    cmd = [
        sys.executable, "-m", "flake8",
        "shit_tests/",
        "--max-line-length=100",
        "--ignore=E203,W503"
    ]
    return run_command(cmd, "Lint Tests")


def type_check_tests():
    """Type check test files."""
    cmd = [
        sys.executable, "-m", "mypy",
        "shit_tests/",
        "--ignore-missing-imports"
    ]
    return run_command(cmd, "Type Check Tests")


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description="Shitpost Alpha Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py unit                    # Run unit tests
  python run_tests.py integration            # Run integration tests
  python run_tests.py e2e                    # Run end-to-end tests
  python run_tests.py all                    # Run all tests
  python run_tests.py coverage               # Run tests with coverage
  python run_tests.py specific test_file.py  # Run specific test
  python run_tests.py parallel               # Run tests in parallel
  python run_tests.py slow                   # Run slow tests
  python run_tests.py install                # Install test dependencies
  python run_tests.py lint                   # Lint test files
  python run_tests.py typecheck              # Type check test files
        """
    )
    
    parser.add_argument(
        "command",
        choices=[
            "unit", "integration", "e2e", "all", "coverage",
            "specific", "parallel", "slow", "install", "lint", "typecheck"
        ],
        help="Test command to run"
    )
    
    parser.add_argument(
        "test_path",
        nargs="?",
        help="Path to specific test file (for 'specific' command)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Change to project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("🧪 Shitpost Alpha Test Runner")
    print(f"📁 Working directory: {project_root}")
    
    success = False
    
    if args.command == "unit":
        success = run_unit_tests()
    elif args.command == "integration":
        success = run_integration_tests()
    elif args.command == "e2e":
        success = run_e2e_tests()
    elif args.command == "all":
        success = run_all_tests()
    elif args.command == "coverage":
        success = run_tests_with_coverage()
    elif args.command == "specific":
        if not args.test_path:
            print("❌ Error: test_path is required for 'specific' command")
            sys.exit(1)
        success = run_specific_test(args.test_path)
    elif args.command == "parallel":
        success = run_parallel_tests()
    elif args.command == "slow":
        success = run_slow_tests()
    elif args.command == "install":
        success = install_test_dependencies()
    elif args.command == "lint":
        success = lint_tests()
    elif args.command == "typecheck":
        success = type_check_tests()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
