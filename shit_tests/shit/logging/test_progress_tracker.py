"""
Tests for progress tracker utilities.
Tests that will break if progress tracking functionality changes.
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from shit.logging.progress_tracker import (
    ProgressTracker,
    track_progress,
    simple_progress
)
from shit.logging.formatters import Colors, Icons


class TestProgressTracker:
    """Test ProgressTracker class."""
    
    @pytest.fixture
    def progress_tracker_with_total(self):
        """Progress tracker with total count."""
        return ProgressTracker(
            total=100,
            prefix="Processing",
            suffix="items",
            show_percentage=True,
            enable_colors=True
        )
    
    @pytest.fixture
    def progress_tracker_without_total(self):
        """Progress tracker without total count."""
        return ProgressTracker(
            prefix="Processing",
            suffix="items",
            show_percentage=False,
            enable_colors=False
        )
    
    def test_progress_tracker_initialization_with_total(self, progress_tracker_with_total):
        """Test progress tracker initialization with total."""
        assert progress_tracker_with_total.total == 100
        assert progress_tracker_with_total.current == 0
        assert progress_tracker_with_total.prefix == "Processing"
        assert progress_tracker_with_total.suffix == "items"
        assert progress_tracker_with_total.show_percentage is True
        assert progress_tracker_with_total.enable_colors is True
        assert isinstance(progress_tracker_with_total.start_time, datetime)
        assert isinstance(progress_tracker_with_total.last_update, datetime)
    
    def test_progress_tracker_initialization_without_total(self, progress_tracker_without_total):
        """Test progress tracker initialization without total."""
        assert progress_tracker_without_total.total is None
        assert progress_tracker_without_total.current == 0
        assert progress_tracker_without_total.prefix == "Processing"
        assert progress_tracker_without_total.suffix == "items"
        assert progress_tracker_without_total.show_percentage is False
        assert progress_tracker_without_total.enable_colors is False
    
    def test_progress_tracker_default_initialization(self):
        """Test progress tracker with default parameters."""
        tracker = ProgressTracker()
        assert tracker.total is None
        assert tracker.current == 0
        assert tracker.prefix == ""
        assert tracker.suffix == ""
        assert tracker.show_percentage is True
        assert tracker.enable_colors is True
    
    @patch('builtins.print')
    def test_update_with_total_and_colors(self, mock_print, progress_tracker_with_total):
        """Test update method with total and colors enabled."""
        progress_tracker_with_total.update(10, "Starting")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain progress information
        assert "Processing" in call_args
        assert "10/100" in call_args
        assert "(10.0%)" in call_args
        assert "Starting" in call_args
        assert "items" in call_args
        assert "📊" in call_args  # Progress icon
    
    @patch('builtins.print')
    def test_update_without_total_and_colors(self, mock_print, progress_tracker_without_total):
        """Test update method without total and colors disabled."""
        progress_tracker_without_total.update(5, "Working")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain progress information
        assert "Processing" in call_args
        assert "5" in call_args
        assert "Working" in call_args
        assert "items" in call_args
        assert "📊" in call_args  # Progress icon
        # Should not contain percentage
        assert "(" not in call_args or "%)" not in call_args
    
    @patch('builtins.print')
    def test_update_without_status(self, mock_print, progress_tracker_with_total):
        """Test update method without status message."""
        progress_tracker_with_total.update(25)
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain progress information but no status
        assert "Processing" in call_args
        assert "25/100" in call_args
        assert "(25.0%)" in call_args
        assert "items" in call_args
    
    @patch('builtins.print')
    def test_update_with_custom_increment(self, mock_print, progress_tracker_with_total):
        """Test update method with custom increment."""
        progress_tracker_with_total.update(5, "Batch 1")
        progress_tracker_with_total.update(15, "Batch 2")
        
        # Verify total current is correct
        assert progress_tracker_with_total.current == 20
        
        # Verify second call
        second_call = mock_print.call_args_list[1][0][0]
        assert "20/100" in second_call
        assert "(20.0%)" in second_call
        assert "Batch 2" in second_call
    
    @patch('builtins.print')
    def test_finish_with_total(self, mock_print, progress_tracker_with_total):
        """Test finish method with total."""
        progress_tracker_with_total.current = 100
        progress_tracker_with_total.finish("All done!")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain completion information
        assert "✅" in call_args  # Success icon
        assert "Processing" in call_args
        assert "Completed 100/100" in call_args
        assert "All done!" in call_args
        assert "in" in call_args  # Elapsed time
    
    @patch('builtins.print')
    def test_finish_without_total(self, mock_print, progress_tracker_without_total):
        """Test finish method without total."""
        progress_tracker_without_total.current = 50
        progress_tracker_without_total.finish("Done!")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain completion information
        assert "✅" in call_args  # Success icon
        assert "Processing" in call_args
        assert "Completed 50 items" in call_args
        assert "Done!" in call_args
        assert "in" in call_args  # Elapsed time
    
    @patch('builtins.print')
    def test_finish_without_status(self, mock_print, progress_tracker_with_total):
        """Test finish method without status message."""
        progress_tracker_with_total.current = 100
        progress_tracker_with_total.finish()
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain completion information but no status
        assert "✅" in call_args  # Success icon
        assert "Processing" in call_args
        assert "Completed 100/100" in call_args
        assert "in" in call_args  # Elapsed time
    
    @patch('builtins.print')
    def test_error_method(self, mock_print, progress_tracker_with_total):
        """Test error method."""
        progress_tracker_with_total.error("Something went wrong!")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain error information
        assert "❌" in call_args  # Error icon
        assert "Processing" in call_args
        assert "Something went wrong!" in call_args
    
    @patch('builtins.print')
    def test_update_updates_last_update_time(self, mock_print, progress_tracker_with_total):
        """Test that update method updates last_update time."""
        initial_time = progress_tracker_with_total.last_update
        progress_tracker_with_total.update(10)
        
        # Should have updated last_update time
        assert progress_tracker_with_total.last_update > initial_time
    
    def test_progress_tracker_with_zero_total(self):
        """Test progress tracker with zero total raises exception."""
        tracker = ProgressTracker(total=0, show_percentage=True)
        
        # Should raise ZeroDivisionError when trying to calculate percentage
        with pytest.raises(ZeroDivisionError):
            tracker.update(0)
    
    def test_progress_tracker_with_negative_increment(self):
        """Test progress tracker with negative increment."""
        tracker = ProgressTracker(total=100)
        tracker.current = 50
        
        with patch('builtins.print') as mock_print:
            tracker.update(-10)
            assert tracker.current == 40
            call_args = mock_print.call_args[0][0]
            assert "40/100" in call_args


class TestTrackProgress:
    """Test track_progress function."""
    
    def test_track_progress_with_all_parameters(self):
        """Test track_progress with all parameters."""
        tracker = track_progress(
            total=50,
            prefix="Test",
            suffix="items",
            show_percentage=True
        )
        
        assert isinstance(tracker, ProgressTracker)
        assert tracker.total == 50
        assert tracker.prefix == "Test"
        assert tracker.suffix == "items"
        assert tracker.show_percentage is True
    
    def test_track_progress_with_minimal_parameters(self):
        """Test track_progress with minimal parameters."""
        tracker = track_progress()
        
        assert isinstance(tracker, ProgressTracker)
        assert tracker.total is None
        assert tracker.prefix == ""
        assert tracker.suffix == ""
        assert tracker.show_percentage is True
    
    def test_track_progress_without_total(self):
        """Test track_progress without total."""
        tracker = track_progress(
            prefix="Processing",
            suffix="files",
            show_percentage=False
        )
        
        assert isinstance(tracker, ProgressTracker)
        assert tracker.total is None
        assert tracker.prefix == "Processing"
        assert tracker.suffix == "files"
        assert tracker.show_percentage is False


class TestSimpleProgress:
    """Test simple_progress function."""
    
    @patch('builtins.print')
    def test_simple_progress_with_total(self, mock_print):
        """Test simple_progress with total."""
        simple_progress(25, 100, "Processing files")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain progress information
        assert "📊" in call_args  # Progress icon
        assert "Processing files: 25/100 (25.0%)" in call_args
    
    @patch('builtins.print')
    def test_simple_progress_without_total(self, mock_print):
        """Test simple_progress without total."""
        simple_progress(25, None, "Processing files")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain progress information
        assert "📊" in call_args  # Progress icon
        assert "Processing files: 25" in call_args
    
    @patch('builtins.print')
    def test_simple_progress_with_default_message(self, mock_print):
        """Test simple_progress with default message."""
        simple_progress(10, 20)
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain default message
        assert "Processing: 10/20 (50.0%)" in call_args
    
    @patch('builtins.print')
    def test_simple_progress_with_zero_total(self, mock_print):
        """Test simple_progress with zero total raises exception."""
        # Should raise ZeroDivisionError when trying to calculate percentage
        with pytest.raises(ZeroDivisionError):
            simple_progress(0, 0, "Test")
    
    @patch('builtins.print')
    def test_simple_progress_with_unicode_message(self, mock_print):
        """Test simple_progress with unicode message."""
        simple_progress(5, 10, "测试进度")
        
        # Verify print was called
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        
        # Should contain unicode message
        assert "测试进度: 5/10 (50.0%)" in call_args


class TestProgressTrackerEdgeCases:
    """Test edge cases and error scenarios for progress tracker."""
    
    def test_progress_tracker_with_very_large_total(self):
        """Test progress tracker with very large total."""
        tracker = ProgressTracker(total=1000000)
        
        with patch('builtins.print') as mock_print:
            tracker.update(500000)
            call_args = mock_print.call_args[0][0]
            assert "500000/1000000" in call_args
            assert "(50.0%)" in call_args
    
    def test_progress_tracker_with_very_long_prefix(self):
        """Test progress tracker with very long prefix."""
        long_prefix = "A" * 100
        tracker = ProgressTracker(prefix=long_prefix)
        
        with patch('builtins.print') as mock_print:
            tracker.update(10)
            call_args = mock_print.call_args[0][0]
            assert long_prefix in call_args
    
    def test_progress_tracker_with_very_long_suffix(self):
        """Test progress tracker with very long suffix."""
        long_suffix = "B" * 100
        tracker = ProgressTracker(suffix=long_suffix)
        
        with patch('builtins.print') as mock_print:
            tracker.update(10)
            call_args = mock_print.call_args[0][0]
            assert long_suffix in call_args
    
    def test_progress_tracker_with_special_characters(self):
        """Test progress tracker with special characters."""
        tracker = ProgressTracker(
            prefix="Test with special chars: !@#$%^&*()",
            suffix="files with spaces and symbols"
        )
        
        with patch('builtins.print') as mock_print:
            tracker.update(10, "Status with émojis 🚀")
            call_args = mock_print.call_args[0][0]
            assert "Test with special chars: !@#$%^&*()" in call_args
            assert "files with spaces and symbols" in call_args
            assert "Status with émojis 🚀" in call_args
    
    def test_progress_tracker_finish_with_zero_elapsed_time(self):
        """Test progress tracker finish with zero elapsed time."""
        tracker = ProgressTracker()
        
        with patch('builtins.print') as mock_print:
            # Mock datetime to return same time for start and finish
            with patch('shit.logging.progress_tracker.datetime') as mock_datetime:
                now = datetime.now()
                mock_datetime.now.return_value = now
                mock_datetime.side_effect = lambda *args, **kwargs: now
                
                tracker.finish("Done")
                call_args = mock_print.call_args[0][0]
                assert "in 0.0s" in call_args
    
    def test_progress_tracker_with_unicode_prefix_suffix(self):
        """Test progress tracker with unicode prefix and suffix."""
        tracker = ProgressTracker(
            prefix="测试前缀",
            suffix="测试后缀"
        )
        
        with patch('builtins.print') as mock_print:
            tracker.update(10, "测试状态")
            call_args = mock_print.call_args[0][0]
            assert "测试前缀" in call_args
            assert "测试后缀" in call_args
            assert "测试状态" in call_args
    
    def test_simple_progress_with_negative_current(self):
        """Test simple_progress with negative current."""
        with patch('builtins.print') as mock_print:
            simple_progress(-5, 10, "Test")
            call_args = mock_print.call_args[0][0]
            assert "Test: -5/10 (-50.0%)" in call_args
    
    def test_simple_progress_with_negative_total(self):
        """Test simple_progress with negative total."""
        with patch('builtins.print') as mock_print:
            simple_progress(5, -10, "Test")
            call_args = mock_print.call_args[0][0]
            assert "Test: 5/-10 (-50.0%)" in call_args
    
    def test_progress_tracker_with_empty_strings(self):
        """Test progress tracker with empty strings."""
        tracker = ProgressTracker(prefix="", suffix="")
        
        with patch('builtins.print') as mock_print:
            tracker.update(10, "")
            call_args = mock_print.call_args[0][0]
            # Should not contain empty prefix/suffix
            assert "10" in call_args
            assert "📊" in call_args
    
    def test_progress_tracker_with_none_values(self):
        """Test progress tracker with None values."""
        tracker = ProgressTracker(prefix=None, suffix=None)
        
        with patch('builtins.print') as mock_print:
            tracker.update(10, None)
            call_args = mock_print.call_args[0][0]
            # Should handle None values gracefully
            assert "10" in call_args
            assert "📊" in call_args


class TestProgressTrackerIntegration:
    """Test progress tracker integration scenarios."""
    
    @patch('builtins.print')
    def test_complete_workflow_with_total(self, mock_print):
        """Test complete workflow with total."""
        tracker = ProgressTracker(
            total=10,
            prefix="Processing",
            suffix="files",
            show_percentage=True
        )
        
        # Simulate processing
        for i in range(1, 11):
            tracker.update(1, f"Processing file {i}")
        
        tracker.finish("All files processed!")
        
        # Verify all updates were called
        assert mock_print.call_count == 11  # 10 updates + 1 finish
        
        # Verify final state
        assert tracker.current == 10
        
        # Verify finish message
        finish_call = mock_print.call_args_list[-1][0][0]
        assert "✅" in finish_call
        assert "Completed 10/10" in finish_call
        assert "All files processed!" in finish_call
    
    @patch('builtins.print')
    def test_complete_workflow_without_total(self, mock_print):
        """Test complete workflow without total."""
        tracker = ProgressTracker(
            prefix="Processing",
            suffix="items",
            show_percentage=False
        )
        
        # Simulate processing
        for i in range(1, 6):
            tracker.update(1, f"Processing item {i}")
        
        tracker.finish("All items processed!")
        
        # Verify all updates were called
        assert mock_print.call_count == 6  # 5 updates + 1 finish
        
        # Verify final state
        assert tracker.current == 5
        
        # Verify finish message
        finish_call = mock_print.call_args_list[-1][0][0]
        assert "✅" in finish_call
        assert "Completed 5 items" in finish_call
        assert "All items processed!" in finish_call
    
    @patch('builtins.print')
    def test_error_handling_workflow(self, mock_print):
        """Test error handling workflow."""
        tracker = ProgressTracker(total=10, prefix="Processing")
        
        # Simulate some progress
        tracker.update(3, "Processing...")
        tracker.update(2, "More processing...")
        
        # Simulate error
        tracker.error("Connection failed!")
        
        # Verify error was logged
        error_call = mock_print.call_args_list[-1][0][0]
        assert "❌" in error_call
        assert "Connection failed!" in error_call
        
        # Verify current state is preserved
        assert tracker.current == 5
