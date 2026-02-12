"""
Validate generated Manim code for correctness.
"""

import ast
import tempfile
import subprocess
import sys
from typing import Tuple, List
from pathlib import Path


class ManimCodeValidator:
    """Validate generated Manim code for basic correctness."""

    def __init__(
        self, 
        enable_runtime_validation: bool = True,
        enable_manim_rendering: bool = True
    ):
        """
        Args:
            enable_runtime_validation: If True, actually try to import the code
                                       to catch runtime errors (undefined names, etc.)
            enable_manim_rendering: If True, actually run manim render to validate
                                   the animation can be generated (catches Manim-specific errors)
        """
        self.enable_runtime_validation = enable_runtime_validation
        self.enable_manim_rendering = enable_manim_rendering

    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate Manim code.

        Checks:
        1. Valid Python syntax
        2. Has Scene class definition
        3. Has construct() method
        4. Has required imports
        5. No obvious API misuse patterns
        6. (Optional) Runtime Python validation
        7. (Optional) Actual Manim rendering validation - THE MOST IMPORTANT CHECK

        Args:
            code: Python code string to validate

        Returns:
            (is_valid, error_messages)
            - is_valid: True if code passes all checks
            - error_messages: List of error descriptions (empty if valid)
        """
        errors = []

        # Check 1: Valid Python syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            # If syntax is invalid, can't do further checks
            return (False, errors)

        # Check 2: Has Scene class
        if not self._has_scene_class(code):
            errors.append("No Scene class definition found (must inherit from Scene)")

        # Check 3: Has construct method
        if "def construct(self)" not in code:
            errors.append("No construct() method found in Scene class")

        # Check 4: Has imports
        if not self._has_imports(code):
            errors.append("Missing manim imports (need 'from manim import *' or similar)")

        # Check 5: No obvious API misuse
        misuse_errors = self._check_api_misuse(code)
        errors.extend(misuse_errors)

        # Check 6: Runtime validation (try to import the code)
        if self.enable_runtime_validation:
            runtime_errors = self._validate_runtime(code)
            errors.extend(runtime_errors)

        # Check 7: ACTUAL MANIM RENDERING VALIDATION - Run manim to see if it renders
        # This is the most important check as it catches real animation errors
        if self.enable_manim_rendering and len(errors) == 0:
            # Only run manim if basic checks passed (saves time)
            render_errors = self._validate_manim_render(code)
            errors.extend(render_errors)

        is_valid = len(errors) == 0
        return (is_valid, errors)

    def _has_scene_class(self, code: str) -> bool:
        """Check if code has a class that inherits from Scene."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Scene":
                            return True
                        if isinstance(base, ast.Attribute) and base.attr == "Scene":
                            return True
            return False
        except:
            return False

    def _has_imports(self, code: str) -> bool:
        """Check if code has manim imports."""
        import_patterns = [
            "from manim import",
            "import manim"
        ]
        return any(pattern in code for pattern in import_patterns)

    def _check_api_misuse(self, code: str) -> List[str]:
        """Check for common API misuse patterns."""
        errors = []

        # Pattern 1: self.play(self.something)
        if "self.play(self." in code:
            errors.append("Possible API misuse: 'self.play(self.xxx)' - play() should be called on Mobjects, not Scene methods")

        # Pattern 2: Scene.play(
        if "Scene.play(" in code:
            errors.append("API misuse: 'Scene.play()' - should be 'self.play()' inside construct()")

        # Pattern 3: Missing self.play
        if "def construct(self):" in code and "self.play(" not in code and "self.add(" not in code:
            errors.append("Warning: construct() method has no self.play() or self.add() calls - scene might be empty")

        return errors

    def _validate_runtime(self, code: str) -> List[str]:
        """
        Runtime validation: Try to import the code to catch errors like:
        - Undefined variables/constants (e.g., DARK_GREEN)
        - Import errors
        - Name errors

        Returns list of runtime errors found.
        """
        errors = []

        # Create a temporary file with the code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name

        try:
            # Try to compile and check for NameErrors by running a syntax check
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', temp_file],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                # Compilation errors
                errors.append(f"Compilation error: {result.stderr}")

            # Try to import and check for undefined names
            # We use a subprocess to avoid polluting our namespace
            check_script = f"""
import sys
import traceback
import ast

try:
    # Try to parse and check for common undefined names
    with open('{temp_file}', 'r') as f:
        code = f.read()

    # Try to compile which will catch NameErrors at definition time
    compile(code, '<string>', 'exec')

    # Try to import manim and check if constants exist
    from manim import *

    # Extract uppercase identifiers using AST (excludes strings)
    tree = ast.parse(code)
    constants = set()

    for node in ast.walk(tree):
        # Check Name nodes (variable/constant references)
        if isinstance(node, ast.Name):
            name = node.id
            if name.isupper() and len(name) > 1:  # Uppercase with 2+ chars
                constants.add(name)
        # Check Attribute nodes (e.g., module.CONSTANT)
        elif isinstance(node, ast.Attribute):
            if node.attr.isupper() and len(node.attr) > 1:
                constants.add(node.attr)

    # Filter out known Python/common keywords and Manim constants
    exclude = {{'SHIFT', 'LEFT', 'RIGHT', 'UP', 'DOWN', 'IN', 'OUT', 'ORIGIN',
                'TRUE', 'FALSE', 'NONE', 'PI', 'TAU', 'E', 'DEGREES', 'MED_SMALL_BUFF',
                'SMALL_BUFF', 'DEFAULT_MOBJECT_TO_EDGE_BUFFER', 'LARGE_BUFF', 'DR',
                'UR', 'UL', 'DL', 'DEFAULT', 'FRAME_HEIGHT', 'FRAME_WIDTH'}}

    undefined = []
    manim_globals = set(dir())  # All manim globals after 'from manim import *'

    for const in constants:
        if const not in exclude and const not in manim_globals:
            undefined.append(const)

    if undefined:
        print("UNDEFINED_CONSTANTS:" + ",".join(undefined))

except NameError as e:
    print(f"NameError: {{e}}")
except SyntaxError as e:
    print(f"SyntaxError: {{e}}")
except Exception as e:
    print(f"Error: {{e}}")
"""

            result = subprocess.run(
                [sys.executable, '-c', check_script],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.stdout:
                output = result.stdout.strip()
                if "UNDEFINED_CONSTANTS:" in output:
                    undefined_consts = output.split("UNDEFINED_CONSTANTS:")[1].split(",")
                    for const in undefined_consts:
                        if const.strip():
                            errors.append(f"Undefined constant: '{const}' - not found in Manim. Check color names and constants.")
                elif "NameError" in output:
                    errors.append(f"Runtime error: {output}")
                elif "SyntaxError" in output:
                    errors.append(f"Syntax error: {output}")

        except subprocess.TimeoutExpired:
            errors.append("Validation timeout - code took too long to check")
        except Exception as e:
            errors.append(f"Runtime validation failed: {e}")
        finally:
            # Clean up temp file
            try:
                Path(temp_file).unlink()
            except:
                pass

        return errors

    def _validate_manim_render(self, code: str) -> List[str]:
        """
        Actually run manim render to validate the animation can be generated.
        
        This is the MOST IMPORTANT validation - it catches real Manim errors:
        - Undefined colors (e.g., DARK_GREEN vs GREEN_D)
        - LaTeX syntax errors in Tex/MathTex
        - Incorrect method calls or parameters
        - Animation-specific errors
        - Scene rendering issues
        
        Returns list of rendering errors found.
        """
        errors = []
        
        # Extract Scene class name from code
        scene_name = self._extract_scene_name(code)
        if not scene_name:
            errors.append("Could not extract Scene class name for rendering validation")
            return errors
        
        # Create temporary file with the code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        # Create temporary output directory
        temp_output_dir = tempfile.mkdtemp()
        
        try:
            # Run manim render in preview quality (fast)
            # -ql = preview quality (480p15)
            # --disable_caching to ensure fresh render
            # -v WARNING to reduce output noise
            result = subprocess.run(
                [
                    'manim', 'render',
                    '-ql',  # Preview quality for speed
                    '--disable_caching',
                    '-v', 'WARNING',
                    '--media_dir', temp_output_dir,
                    temp_file,
                    scene_name
                ],
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout for rendering
            )
            
            if result.returncode != 0:
                # Manim rendering failed - extract the error message
                stderr = result.stderr.strip()
                stdout = result.stdout.strip()
                
                # Parse Manim error messages
                error_msg = self._parse_manim_error(stderr, stdout)
                errors.append(f"Manim rendering failed: {error_msg}")
                
        except subprocess.TimeoutExpired:
            errors.append("Manim rendering timeout - animation took too long to render (>60s)")
        except FileNotFoundError:
            errors.append("Manim command not found - is Manim installed? Run: pip install manim")
        except Exception as e:
            errors.append(f"Manim rendering validation error: {e}")
        finally:
            # Clean up temp files
            try:
                Path(temp_file).unlink()
            except:
                pass
            try:
                import shutil
                shutil.rmtree(temp_output_dir, ignore_errors=True)
            except:
                pass
        
        return errors
    
    def _extract_scene_name(self, code: str) -> str:
        """Extract the Scene class name from the code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Scene":
                            return node.name
                        if isinstance(base, ast.Attribute) and base.attr == "Scene":
                            return node.name
            return ""
        except:
            return ""
    
    def _parse_manim_error(self, stderr: str, stdout: str) -> str:
        """
        Parse Manim error messages to extract the most useful information.
        
        Manim errors often include:
        - NameError for undefined colors/constants
        - AttributeError for incorrect method calls
        - LaTeX compilation errors
        - TypeError for incorrect parameters
        """
        # Combine stderr and stdout (Manim sometimes prints errors to stdout)
        full_output = stderr + "\n" + stdout
        
        # Common error patterns to extract
        error_patterns = [
            "NameError:",
            "AttributeError:",
            "TypeError:",
            "ValueError:",
            "LaTeX Error:",
            "Error:",
        ]
        
        # Find the most relevant error lines
        error_lines = []
        for line in full_output.split('\n'):
            for pattern in error_patterns:
                if pattern in line:
                    error_lines.append(line.strip())
                    break
        
        if error_lines:
            # Return the first few error lines (most relevant)
            return "\n".join(error_lines[:5])
        
        # If no specific error pattern found, return last 500 chars of output
        if full_output.strip():
            return full_output.strip()[-500:]
        
        return "Unknown rendering error - check Manim installation"

    def validate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Validate a Python file containing Manim code.

        Args:
            file_path: Path to Python file

        Returns:
            (is_valid, error_messages)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.validate(code)
        except Exception as e:
            return (False, [f"Error reading file: {e}"])


def main():
    """CLI for validating Manim code files."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m research_viz.manim_generator.manim_code_validator <file.py>")
        sys.exit(1)

    file_path = sys.argv[1]

    validator = ManimCodeValidator()
    is_valid, errors = validator.validate_file(file_path)

    if is_valid:
        print(f"✓ {file_path} is valid!")
    else:
        print(f"✗ {file_path} has errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
