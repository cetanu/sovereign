import time
import json
import sys
import os
import pytest
import httpx
import statistics
from typing import Dict, Any, List, Tuple

# Check if we're in a terminal that supports escape codes
# Default to False since many CI/CD environments and redirected outputs don't support escape codes
USE_TERMINAL_ESCAPE_CODES = os.isatty(sys.stdout.fileno())

# Constants for the test
MOCK_URL = "http://localhost:8000"
SOVEREIGN_URL = "http://localhost:80"  # Port 80 maps to 8080 in docker-compose
CONTEXT_VALUES = ["helloworld", "foobar", "test123", "performance"]
NUM_ITERATIONS = 3  # Reduced number of iterations
MAX_WAIT_TIME = 60.0  # Maximum time to wait for context propagation in seconds
RETRY_DELAY = 0.2  # Time to wait between retries in seconds
SERVICE_CHECK_TIMEOUT = 5.0  # Timeout for checking if services are available


def check_service_availability() -> Tuple[bool, bool]:
    """
    Check if the required services (Sovereign and Mock) are available.
    Returns a tuple of (sovereign_available, mock_available).
    """
    sovereign_available = False
    mock_available = False
    
    print("\nChecking service availability...")
    
    # Check Sovereign
    try:
        response = httpx.get(f"{SOVEREIGN_URL}/deepcheck", timeout=SERVICE_CHECK_TIMEOUT)
        if response.status_code == 200:
            sovereign_available = True
            print(f"✅ Sovereign service is available at {SOVEREIGN_URL}")
        else:
            print(f"❌ Sovereign service returned status code {response.status_code}")
    except httpx.RequestError as e:
        print(f"❌ Sovereign service is not available: {str(e)}")
    
    # Check Mock
    try:
        response = httpx.get(f"{MOCK_URL}/context", timeout=SERVICE_CHECK_TIMEOUT)
        if response.status_code == 200:
            mock_available = True
            print(f"✅ Mock service is available at {MOCK_URL}")
        else:
            print(f"❌ Mock service returned status code {response.status_code}")
    except httpx.RequestError as e:
        print(f"❌ Mock service is not available: {str(e)}")
    
    return sovereign_available, mock_available


class TestDiscoveryPerformance:
    """Test the performance of the discovery mechanism."""

    @pytest.fixture
    def discovery_request(self) -> Dict[str, Any]:
        """Load a sample discovery request."""
        with open("samples/discovery_request.json", "r") as f:
            return json.load(f)

    def reset_context(self, context_value: str = "helloworld") -> None:
        """Reset the context to a known value."""
        try:
            response = httpx.patch(f"{MOCK_URL}/context/{context_value}", timeout=5.0)
            if response.status_code == 200:
                print(f"Context reset to '{context_value}'")
            else:
                print(f"Warning: Context reset returned status code {response.status_code}")
        except httpx.RequestError as e:
            print(f"Error resetting context: {str(e)}")

    def update_context(self, new_value: str) -> float:
        """Update the context and return the time it took."""
        start_time = time.time()
        try:
            print(f"Sending context update request to {MOCK_URL}/context/{new_value}")
            response = httpx.patch(f"{MOCK_URL}/context/{new_value}", timeout=5.0)
            if response.status_code == 200:
                print(f"Successfully updated context to '{new_value}'")
            else:
                print(f"Warning: Context update returned status code {response.status_code}")
                
            # Verify the context was updated in the mock service
            verify_response = httpx.get(f"{MOCK_URL}/context", timeout=5.0)
            if verify_response.status_code == 200:
                current_context = verify_response.text.strip('"')
                print(f"Current context in mock service: '{current_context}'")
                if current_context != new_value:
                    print(f"WARNING: Context in mock service doesn't match requested value!")
            else:
                print(f"Warning: Failed to verify context update, status code {verify_response.status_code}")
        except httpx.RequestError as e:
            print(f"Error updating context: {str(e)}")
        return time.time() - start_time

    def check_context_propagation(self, expected_value: str) -> Tuple[bool, float]:
        """
        Check if the context has been propagated to the listeners.
        Returns a tuple of (success, time_taken).
        
        This function will keep trying until the context is propagated or a timeout occurs.
        """
        start_time = time.time()
        max_retries = int(MAX_WAIT_TIME / RETRY_DELAY) + 1  # Calculate max retries based on timeout and delay
        last_message_length = 0
        
        # Print initial waiting message
        print(f"Waiting for context '{expected_value}' to propagate (timeout: {MAX_WAIT_TIME}s, retries: {max_retries})...", end="", flush=True)
        
        # Check the context in the mock service first to confirm it's set correctly
        try:
            mock_response = httpx.get(f"{MOCK_URL}/context", timeout=5.0)
            if mock_response.status_code == 200:
                mock_context = mock_response.text.strip('"')
                print(f"\nMock service context: '{mock_context}'")
                if mock_context != expected_value:
                    print(f"WARNING: Mock service context doesn't match expected value!")
            else:
                print(f"\nWarning: Failed to check mock service context, status code {mock_response.status_code}")
        except httpx.RequestError as e:
            print(f"\nError checking mock service context: {str(e)}")
        
        for attempt in range(1, max_retries + 1):
            elapsed_time = time.time() - start_time
            if elapsed_time > MAX_WAIT_TIME:
                # Clear the current line if using terminal escape codes
                if USE_TERMINAL_ESCAPE_CODES:
                    print("\r" + " " * last_message_length + "\r", end="", flush=True)
                print(f"Timeout after {elapsed_time:.1f} seconds waiting for context '{expected_value}'")
                return False, elapsed_time
            
            try:
                response = httpx.get(f"{SOVEREIGN_URL}/ui/resources/listeners/port80", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    try:
                        actual_value = data["resources"][0]["filter_chains"][0]["filters"][0]["typed_config"]["stat_prefix"]
                        if actual_value == expected_value:
                            elapsed_time = time.time() - start_time
                            # Clear the current line if using terminal escape codes
                            if USE_TERMINAL_ESCAPE_CODES:
                                print("\r" + " " * last_message_length + "\r", end="", flush=True)
                            print(f"Context '{expected_value}' found after {elapsed_time:.3f}s ({attempt} attempts)")
                            return True, elapsed_time
                        else:
                            # Update the status on the same line if using terminal escape codes
                            status_msg = f"Attempt {attempt}: Found '{actual_value}', expecting '{expected_value}' ({elapsed_time:.1f}s)"
                            if USE_TERMINAL_ESCAPE_CODES:
                                print("\r" + " " * last_message_length + "\r" + status_msg, end="", flush=True)
                                last_message_length = len(status_msg)
                            else:
                                print(f"Attempt {attempt}: Found value '{actual_value}', expecting '{expected_value}'")
                    except (KeyError, IndexError) as e:
                        # Update the status on the same line if using terminal escape codes
                        status_msg = f"Attempt {attempt}: Error extracting value ({elapsed_time:.1f}s)"
                        if USE_TERMINAL_ESCAPE_CODES:
                            print("\r" + " " * last_message_length + "\r" + status_msg, end="", flush=True)
                            last_message_length = len(status_msg)
                        else:
                            print(f"Attempt {attempt}: Error extracting value: {str(e)}")
                else:
                    # Update the status on the same line if using terminal escape codes
                    status_msg = f"Attempt {attempt}: HTTP status {response.status_code} ({elapsed_time:.1f}s)"
                    if USE_TERMINAL_ESCAPE_CODES:
                        print("\r" + " " * last_message_length + "\r" + status_msg, end="", flush=True)
                        last_message_length = len(status_msg)
                    else:
                        print(f"Attempt {attempt}: HTTP status {response.status_code}")
            except httpx.RequestError as e:
                # Update the status on the same line if using terminal escape codes
                status_msg = f"Attempt {attempt}: Request error ({elapsed_time:.1f}s)"
                if USE_TERMINAL_ESCAPE_CODES:
                    print("\r" + " " * last_message_length + "\r" + status_msg, end="", flush=True)
                    last_message_length = len(status_msg)
                else:
                    print(f"Attempt {attempt}: Request error: {str(e)}")
            
            # Only sleep if we're going to make another attempt
            if attempt < max_retries:
                time.sleep(RETRY_DELAY)
        
        elapsed_time = time.time() - start_time
        # Clear the current line if using terminal escape codes
        if USE_TERMINAL_ESCAPE_CODES:
            print("\r" + " " * last_message_length + "\r", end="", flush=True)
        print(f"Gave up after {elapsed_time:.1f} seconds and {max_retries} attempts")
        return False, elapsed_time

    def test_context_update_performance(self) -> None:
        """Test the performance of context updates."""
        # Check if services are available
        sovereign_available, mock_available = check_service_availability()
        if not sovereign_available or not mock_available:
            pytest.skip("Required services are not available")
        
        results: List[Dict[str, Any]] = []
        failed_contexts: List[str] = []
        
        # Reset the context to a known state
        print("\nResetting context to initial state...")
        self.reset_context()
        
        # Wait for initial context to be loaded
        print("Checking initial context...")
        initial_success, initial_time = self.check_context_propagation("helloworld")
        assert initial_success, "Failed to initialize context"
        
        print(f"Initial context propagation took {initial_time:.3f} seconds")
        
        # Run the test multiple times
        for iteration in range(NUM_ITERATIONS):
            print(f"\n--- Starting iteration {iteration+1}/{NUM_ITERATIONS} ---")
            iteration_results = []
            
            for context_value in CONTEXT_VALUES:
                print(f"\nTesting context value: {context_value}")
                
                # Start measuring total time from here
                total_start_time = time.time()
                
                # Update the context
                update_time = self.update_context(context_value)
                print(f"Context update request took {update_time:.3f}s")
                
                # Check if the context has been propagated
                success, propagation_time = self.check_context_propagation(context_value)
                
                # Calculate total time (from start of update to end of propagation check)
                total_time = time.time() - total_start_time
                
                if not success:
                    print(f"WARNING: Context '{context_value}' was not propagated after {propagation_time:.3f}s")
                    failed_contexts.append(context_value)
                    continue
                
                result = {
                    "context_value": context_value,
                    "update_time": update_time,
                    "propagation_time": propagation_time,
                    "total_time": total_time  # Use the measured total time
                }
                iteration_results.append(result)
                
                print(f"Iteration {iteration+1}/{NUM_ITERATIONS}, Context: {context_value}, "
                      f"Update: {update_time:.3f}s, Propagation: {propagation_time:.3f}s, "
                      f"Total: {total_time:.3f}s")
            
            if iteration_results:  # Only add if we have results
                results.append({
                    "iteration": iteration + 1,
                    "results": iteration_results
                })
        
        # Check if any contexts failed to propagate
        if failed_contexts:
            error_msg = f"\n\033[91m❌ ERROR: The following contexts failed to propagate: {', '.join(failed_contexts)}\033[0m"
            print(error_msg)
            if __name__ == "__main__":  # Only exit if running as script, not when running via pytest
                sys.exit(1)
            else:
                assert False, f"The following contexts failed to propagate: {', '.join(failed_contexts)}"
        
        # Make sure we have results to analyze
        assert results, "No successful context propagations were recorded"
        
        # Calculate and print statistics
        update_times = [r["update_time"] for iteration in results for r in iteration["results"]]
        propagation_times = [r["propagation_time"] for iteration in results for r in iteration["results"]]
        total_times = [r["total_time"] for iteration in results for r in iteration["results"]]
        
        print("\nPerformance Statistics:")
        print(f"Update Time (s): min={min(update_times):.3f}, max={max(update_times):.3f}, "
              f"mean={statistics.mean(update_times):.3f}, median={statistics.median(update_times):.3f}")
        print(f"Propagation Time (s): min={min(propagation_times):.3f}, max={max(propagation_times):.3f}, "
              f"mean={statistics.mean(propagation_times):.3f}, median={statistics.median(propagation_times):.3f}")
        print(f"Total Time (s): min={min(total_times):.3f}, max={max(total_times):.3f}, "
              f"mean={statistics.mean(total_times):.3f}, median={statistics.median(total_times):.3f}")
        
        # Assert that the performance is within acceptable limits
        # These thresholds can be adjusted based on expected performance
        assert statistics.median(total_times) < 30.0, "Context update and propagation is too slow"


class TestDiscoveryRequestPerformance:
    """Test the performance of direct discovery requests."""
    
    @pytest.fixture
    def discovery_request(self) -> Dict[str, Any]:
        """Load a sample discovery request."""
        with open("samples/discovery_request.json", "r") as f:
            return json.load(f)
    
    def reset_context(self, context_value: str = "helloworld") -> None:
        """Reset the context to a known value."""
        try:
            response = httpx.patch(f"{MOCK_URL}/context/{context_value}", timeout=5.0)
            if response.status_code == 200:
                print(f"Context reset to '{context_value}'")
            else:
                print(f"Warning: Context reset returned status code {response.status_code}")
        except httpx.RequestError as e:
            print(f"Error resetting context: {str(e)}")
    
    def make_discovery_request(self, request_data: Dict[str, Any], resource_type: str) -> Tuple[Dict[str, Any], float]:
        """Make a discovery request and return the response and time taken."""
        start_time = time.time()
        try:
            response = httpx.post(
                f"{SOVEREIGN_URL}/v3/discovery:{resource_type}",
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            time_taken = time.time() - start_time
            
            if response.status_code != 200:
                print(f"Warning: Discovery request returned status code {response.status_code}")
                return {"error": f"HTTP {response.status_code}", "version_info": "error"}, time_taken
                
            return response.json(), time_taken
        except httpx.RequestError as e:
            time_taken = time.time() - start_time
            print(f"Error making discovery request: {str(e)}")
            return {"error": str(e), "version_info": "error"}, time_taken
    
    def test_listeners_discovery_performance(self, discovery_request: Dict[str, Any]) -> None:
        """Test the performance of listeners discovery requests."""
        # Check if services are available
        sovereign_available, _ = check_service_availability()
        if not sovereign_available:
            pytest.skip("Sovereign service is not available")
            
        results = []
        
        # Reset the context to a known state
        self.reset_context()
        
        # Make multiple requests to measure performance
        for i in range(NUM_ITERATIONS):
            # Clone the request to avoid modifying the original
            request = json.loads(json.dumps(discovery_request))
            request["resource_names"] = ["port80"]
            
            response, time_taken = self.make_discovery_request(request, "listeners")
            
            results.append({
                "iteration": i + 1,
                "time_taken": time_taken,
                "version_info": response.get("version_info", "unknown")
            })
            
            print(f"Listeners Discovery Request {i+1}/{NUM_ITERATIONS}: {time_taken:.3f}s, "
                  f"Version: {response.get('version_info', 'unknown')}")
        
        # Calculate and print statistics
        times = [r["time_taken"] for r in results]
        
        print("\nListeners Discovery Performance Statistics:")
        print(f"Time (s): min={min(times):.3f}, max={max(times):.3f}, "
              f"mean={statistics.mean(times):.3f}, median={statistics.median(times):.3f}")
        
        # Assert that the performance is within acceptable limits
        assert statistics.median(times) < 1.0, "Listeners discovery requests are too slow"
    
    def test_routes_discovery_performance(self, discovery_request: Dict[str, Any]) -> None:
        """Test the performance of routes discovery requests."""
        # Check if services are available
        sovereign_available, _ = check_service_availability()
        if not sovereign_available:
            pytest.skip("Sovereign service is not available")
            
        results = []
        
        # Reset the context to a known state
        self.reset_context()
        
        # Make multiple requests to measure performance
        for i in range(NUM_ITERATIONS):
            # Clone the request to avoid modifying the original
            request = json.loads(json.dumps(discovery_request))
            request["resource_names"] = ["rds"]
            
            response, time_taken = self.make_discovery_request(request, "routes")
            
            results.append({
                "iteration": i + 1,
                "time_taken": time_taken,
                "version_info": response.get("version_info", "unknown")
            })
            
            print(f"Routes Discovery Request {i+1}/{NUM_ITERATIONS}: {time_taken:.3f}s, "
                  f"Version: {response.get('version_info', 'unknown')}")
        
        # Calculate and print statistics
        times = [r["time_taken"] for r in results]
        
        print("\nRoutes Discovery Performance Statistics:")
        print(f"Time (s): min={min(times):.3f}, max={max(times):.3f}, "
              f"mean={statistics.mean(times):.3f}, median={statistics.median(times):.3f}")
        
        # Assert that the performance is within acceptable limits
        assert statistics.median(times) < 1.0, "Routes discovery requests are too slow"


def run_tests(skip_checks: bool = False) -> int:
    """
    Run all the performance tests.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    has_failures = False
    
    if not skip_checks:
        sovereign_available, mock_available = check_service_availability()
        
        if not sovereign_available:
            print("\n⚠️  WARNING: Sovereign service is not available!")
            print(f"Make sure the Sovereign service is running on {SOVEREIGN_URL}")
            print("You can start it with: docker-compose up -d sovereign")
            if not mock_available:
                print("\n⚠️  WARNING: Mock service is not available!")
                print("Make sure the Mock service is running on http://localhost:8000")
                print("You can start it with: docker-compose up -d mock")
                print("\n❌ Cannot run tests without both services available.")
                return 1
            print("\n⚠️  Skipping tests that require Sovereign service.")
            return 1
        
        if not mock_available:
            print("\n⚠️  WARNING: Mock service is not available!")
            print("Make sure the Mock service is running on http://localhost:8000")
            print("You can start it with: docker-compose up -d mock")
            print("\n⚠️  Skipping tests that require Mock service.")
            return 1
    
    print("\n🚀 Running performance tests...")
    
    test_discovery = TestDiscoveryRequestPerformance()
    with open("samples/discovery_request.json", "r") as f:
        discovery_request = json.load(f)
    try:
        print("\n📊 Testing context update performance...")
        test = TestDiscoveryPerformance()
        test.test_context_update_performance()
    except Exception as e:
        print(f"\n\033[91m❌ Context update performance test failed: {str(e)}\033[0m")
        has_failures = True
    
    try:
        print("\n📊 Testing listeners discovery performance...")
        # Load discovery request directly instead of using pytest fixture
        test_discovery.test_listeners_discovery_performance(discovery_request)
    except Exception as e:
        print(f"\n\033[91m❌ Listeners discovery performance test failed: {str(e)}\033[0m")
        has_failures = True
    
    try:
        print("\n📊 Testing routes discovery performance...")
        test_discovery.test_routes_discovery_performance(discovery_request)
    except Exception as e:
        print(f"\n\033[91m❌ Routes discovery performance test failed: {str(e)}\033[0m")
        has_failures = True
    
    if has_failures:
        print("\n\033[91m❌ Performance tests completed with failures!\033[0m")
        return 1
    else:
        print("\n\033[92m✅ Performance tests completed successfully!\033[0m")
        return 0


if __name__ == "__main__":
    # This allows running the tests directly without pytest
    import argparse
    
    parser = argparse.ArgumentParser(description="Run discovery performance tests")
    parser.add_argument("--skip-checks", action="store_true", help="Skip service availability checks")
    parser.add_argument("--single-line", action="store_true", 
                      help="Use terminal escape codes to update status on a single line (may not work in all terminals)")
    args = parser.parse_args()
    
    # Enable single-line mode if requested
    if args.single_line:
        USE_TERMINAL_ESCAPE_CODES = True
    
    # Run tests and exit with the appropriate exit code
    exit_code = run_tests(skip_checks=args.skip_checks)
    sys.exit(exit_code)
