"""
Progress Tracker
Provides real-time progress tracking for operations.
"""

import sys
from typing import Optional
from datetime import datetime

from .formatters import print_info, Colors, Icons, colorize


class ProgressTracker:
    """Tracks and displays progress for long-running operations."""
    
    def __init__(
        self,
        total: Optional[int] = None,
        prefix: str = "",
        suffix: str = "",
        show_percentage: bool = True,
        enable_colors: bool = True
    ):
        """Initialize progress tracker.
        
        Args:
            total: Total number of items (optional)
            prefix: Prefix to display before progress
            suffix: Suffix to display after progress
            show_percentage: Whether to show percentage
            enable_colors: Whether to enable color output
        """
        self.total = total
        self.current = 0
        self.prefix = prefix
        self.suffix = suffix
        self.show_percentage = show_percentage
        self.enable_colors = enable_colors
        self.start_time = datetime.now()
        self.last_update = datetime.now()
    
    def update(self, increment: int = 1, status: Optional[str] = None):
        """Update progress.
        
        Args:
            increment: Amount to increment progress by
            status: Optional status message to display
        """
        self.current += increment
        
        # Build progress message
        parts = []
        
        # Icon and prefix
        if self.prefix:
            parts.append(self.prefix)
        
        # Progress counter
        if self.total is not None:
            progress_str = f"{self.current}/{self.total}"
            if self.enable_colors:
                progress_str = colorize(progress_str, Colors.BRIGHT_BLUE)
            parts.append(progress_str)
            
            # Percentage
            if self.show_percentage:
                percentage = (self.current / self.total) * 100
                percentage_str = f"({percentage:.1f}%)"
                if self.enable_colors:
                    percentage_str = colorize(percentage_str, Colors.BRIGHT_GREEN)
                parts.append(percentage_str)
        else:
            progress_str = f"{self.current}"
            if self.enable_colors:
                progress_str = colorize(progress_str, Colors.BRIGHT_BLUE)
            parts.append(progress_str)
        
        # Status
        if status:
            parts.append(status)
        
        # Suffix
        if self.suffix:
            parts.append(self.suffix)
        
        # Build and print message
        message = " ".join(parts)
        
        # Add progress icon
        icon = Icons.PROGRESS if hasattr(Icons, 'PROGRESS') else "📊"
        if self.enable_colors:
            icon = colorize(icon, Colors.BRIGHT_CYAN)
        
        print(f"{icon} {message}")
        
        # Update last update time
        self.last_update = datetime.now()
    
    def finish(self, status: Optional[str] = None):
        """Finish progress tracking.
        
        Args:
            status: Optional completion status message
        """
        # Calculate elapsed time
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Build completion message
        parts = []
        
        # Success icon
        icon = Icons.SUCCESS
        if self.enable_colors:
            icon = colorize(icon, Colors.BRIGHT_GREEN)
        parts.append(icon)
        
        # Prefix
        if self.prefix:
            parts.append(self.prefix)
        
        # Completion counter
        if self.total is not None:
            completion_str = f"Completed {self.current}/{self.total}"
            if self.enable_colors:
                completion_str = colorize(completion_str, Colors.BRIGHT_GREEN)
            parts.append(completion_str)
        else:
            completion_str = f"Completed {self.current} items"
            if self.enable_colors:
                completion_str = colorize(completion_str, Colors.BRIGHT_GREEN)
            parts.append(completion_str)
        
        # Elapsed time
        elapsed_str = f"in {elapsed:.1f}s"
        if self.enable_colors:
            elapsed_str = colorize(elapsed_str, Colors.DIM)
        parts.append(elapsed_str)
        
        # Status
        if status:
            parts.append(status)
        
        # Print completion message
        print(" ".join(parts))
    
    def error(self, error_msg: str):
        """Display error message.
        
        Args:
            error_msg: Error message to display
        """
        icon = Icons.ERROR
        if self.enable_colors:
            icon = colorize(icon, Colors.BRIGHT_RED)
        
        print(f"{icon} {self.prefix} {error_msg}")


def track_progress(
    total: Optional[int] = None,
    prefix: str = "",
    suffix: str = "",
    show_percentage: bool = True
) -> ProgressTracker:
    """Create a progress tracker.
    
    Args:
        total: Total number of items (optional)
        prefix: Prefix to display before progress
        suffix: Suffix to display after progress
        show_percentage: Whether to show percentage
        
    Returns:
        ProgressTracker instance
    """
    return ProgressTracker(
        total=total,
        prefix=prefix,
        suffix=suffix,
        show_percentage=show_percentage
    )


def simple_progress(current: int, total: Optional[int] = None, message: str = "Processing"):
    """Print a simple progress message.
    
    Args:
        current: Current progress
        total: Total items (optional)
        message: Progress message
    """
    if total is not None:
        percentage = (current / total) * 100
        progress_str = colorize(
            f"{message}: {current}/{total} ({percentage:.1f}%)",
            Colors.BRIGHT_BLUE
        )
    else:
        progress_str = colorize(
            f"{message}: {current}",
            Colors.BRIGHT_BLUE
        )
    
    icon = Icons.PROGRESS if hasattr(Icons, 'PROGRESS') else "📊"
    icon = colorize(icon, Colors.BRIGHT_CYAN)
    
    print(f"{icon} {progress_str}")


# Add PROGRESS icon to Icons class if not present
if not hasattr(Icons, 'PROGRESS'):
    Icons.PROGRESS = "📊"
