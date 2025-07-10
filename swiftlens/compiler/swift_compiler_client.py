"""Swift compiler client for executing swiftc type checking."""

import os
import subprocess
import tempfile
import time


class SwiftCompilerClient:
    """Client for executing Swift compiler type checking operations."""

    # Class-level cache for environment check results
    _environment_cache = None
    _environment_cache_time = 0
    _environment_cache_ttl = 300  # 5 minutes TTL

    def __init__(self, timeout: int = 30):
        """Initialize the Swift compiler client.

        Args:
            timeout: Maximum time in seconds for compilation operations
        """
        self.timeout = timeout
        self.max_timeout = 60  # Hard limit
        self.max_file_size = 1024 * 1024  # 1MB default limit

        # Ensure timeout is within bounds
        if self.timeout > self.max_timeout:
            self.timeout = self.max_timeout

    def check_environment(self) -> tuple[bool, str]:
        """Check if Swift compiler is available and functional.

        Uses caching to avoid repeated expensive environment checks.

        Returns:
            Tuple of (is_available, message)
        """
        current_time = time.time()

        # Check if we have a valid cached result
        if (
            self._environment_cache is not None
            and current_time - self._environment_cache_time < self._environment_cache_ttl
        ):
            return self._environment_cache

        # Perform the actual environment check
        try:
            # Check if xcrun is available
            result = subprocess.run(
                ["xcrun", "--find", "swiftc"], capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                env_result = (False, "xcrun not found or Swift compiler not available")
            else:
                swift_path = result.stdout.strip()
                if not swift_path:
                    env_result = (False, "Swift compiler path not found")
                else:
                    # Test basic swiftc functionality
                    result = subprocess.run(
                        ["xcrun", "swiftc", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if result.returncode != 0:
                        env_result = (False, "Swift compiler not functional")
                    else:
                        version = result.stdout.strip().split("\n")[0]
                        env_result = (True, f"Swift compiler available: {version}")

        except subprocess.TimeoutExpired:
            env_result = (False, "Swift compiler check timed out")
        except Exception as e:
            env_result = (False, f"Error checking Swift compiler: {str(e)}")

        # Cache the result
        self._environment_cache = env_result
        self._environment_cache_time = current_time

        return env_result

    def validate_file_size(self, file_path: str) -> tuple[bool, str]:
        """Validate that file size is within acceptable limits.

        Args:
            file_path: Path to the Swift file

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                size_mb = file_size / (1024 * 1024)
                limit_mb = self.max_file_size / (1024 * 1024)
                return (
                    False,
                    f"File too large: {size_mb:.1f}MB (limit: {limit_mb:.1f}MB)",
                )
            return True, "File size acceptable"
        except Exception as e:
            return False, f"Error checking file size: {str(e)}"

    def typecheck_file(self, file_path: str) -> tuple[bool, str, str]:
        """Execute swiftc -typecheck on a Swift file.

        Args:
            file_path: Path to the Swift file to type check

        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Validate environment first
        env_ok, env_msg = self.check_environment()
        if not env_ok:
            return False, "", f"Environment error: {env_msg}"

        # Validate file exists
        if not os.path.exists(file_path):
            return False, "", f"File not found: {file_path}"

        # Validate file size
        size_ok, size_msg = self.validate_file_size(file_path)
        if not size_ok:
            return False, "", f"File size error: {size_msg}"

        # Convert to absolute path
        abs_file_path = os.path.abspath(file_path)

        try:
            # Execute swiftc -typecheck
            cmd = ["xcrun", "swiftc", "-typecheck", abs_file_path]

            # Secure working directory: use a safe temporary directory instead of file's directory
            # This prevents execution in user-controlled paths that might have malicious content
            with tempfile.TemporaryDirectory(prefix="swift_typecheck_") as safe_workdir:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=safe_workdir,  # Run in controlled temporary directory
                )

            return True, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return False, "", f"Compilation timed out after {self.timeout} seconds"
        except Exception as e:
            return False, "", f"Compilation error: {str(e)}"

    def typecheck_with_project_context(self, file_path: str) -> tuple[bool, str, str]:
        """Execute type checking with project context detection.

        This method attempts to detect Swift Package Manager or Xcode project
        context and compile accordingly.

        Args:
            file_path: Path to the Swift file to type check

        Returns:
            Tuple of (success, stdout, stderr)
        """
        abs_file_path = os.path.abspath(file_path)
        file_dir = os.path.dirname(abs_file_path)

        # Look for Package.swift (Swift Package Manager)
        package_swift = self._find_package_swift(file_dir)
        if package_swift:
            return self._typecheck_with_spm(abs_file_path, package_swift)

        # Look for .xcodeproj (Xcode project)
        xcode_proj = self._find_xcode_project(file_dir)
        if xcode_proj:
            # For now, fall back to basic typecheck for Xcode projects
            # as they require more complex build settings
            return self.typecheck_file(file_path)

        # Fall back to basic typecheck
        return self.typecheck_file(file_path)

    def _find_package_swift(self, start_dir: str) -> str | None:
        """Find Package.swift file in current or parent directories.

        Args:
            start_dir: Directory to start searching from

        Returns:
            Path to Package.swift if found, None otherwise
        """
        current_dir = os.path.abspath(start_dir)

        while current_dir != "/":
            package_path = os.path.join(current_dir, "Package.swift")
            if os.path.exists(package_path):
                return package_path
            current_dir = os.path.dirname(current_dir)

        return None

    def _find_xcode_project(self, start_dir: str) -> str | None:
        """Find .xcodeproj in current or parent directories.

        Args:
            start_dir: Directory to start searching from

        Returns:
            Path to .xcodeproj if found, None otherwise
        """
        current_dir = os.path.abspath(start_dir)

        while current_dir != "/":
            for item in os.listdir(current_dir):
                if item.endswith(".xcodeproj"):
                    return os.path.join(current_dir, item)
            current_dir = os.path.dirname(current_dir)

        return None

    def _typecheck_with_spm(self, file_path: str, package_swift_path: str) -> tuple[bool, str, str]:
        """Type check file within Swift Package Manager context.

        Args:
            file_path: Path to Swift file
            package_swift_path: Path to Package.swift

        Returns:
            Tuple of (success, stdout, stderr)
        """
        package_dir = os.path.dirname(package_swift_path)

        # Security validation: ensure package directory is safe
        try:
            # Validate the package directory path
            safe_package_dir = os.path.realpath(package_dir)
            if not os.path.exists(safe_package_dir):
                return self.typecheck_file(file_path)

            # Ensure Package.swift exists in the validated directory
            validated_package_swift = os.path.join(safe_package_dir, "Package.swift")
            if not os.path.exists(validated_package_swift):
                return self.typecheck_file(file_path)

        except (OSError, ValueError):
            # Fall back to basic typecheck if path validation fails
            return self.typecheck_file(file_path)

        try:
            # Try using swift build with typecheck-only
            cmd = ["xcrun", "swift", "build", "--build-tests", "-Xswiftc", "-typecheck"]

            # Use the validated package directory
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=safe_package_dir,
            )

            # If SPM build fails, fall back to basic typecheck
            if result.returncode != 0:
                return self.typecheck_file(file_path)

            return True, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return False, "", f"SPM compilation timed out after {self.timeout} seconds"
        except Exception:
            # Fall back to basic typecheck if SPM approach fails
            return self.typecheck_file(file_path)
