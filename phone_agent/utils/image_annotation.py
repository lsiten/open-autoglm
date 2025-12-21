"""Utilities for annotating screenshots with click positions."""

import base64
from io import BytesIO
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


def annotate_click_position(
    screenshot_base64: str, 
    x: int, 
    y: int, 
    screenshot_width: int, 
    screenshot_height: int,
    actual_screen_width: int | None = None,
    actual_screen_height: int | None = None
) -> str:
    """
    Annotate a screenshot with a click position marker.
    
    Args:
        screenshot_base64: Base64-encoded screenshot image
        x: Click X coordinate (in actual screen coordinates)
        y: Click Y coordinate (in actual screen coordinates)
        screenshot_width: Width of the screenshot image
        screenshot_height: Height of the screenshot image
        actual_screen_width: Actual screen width (if screenshot is resized)
        actual_screen_height: Actual screen height (if screenshot is resized)
    
    Returns:
        Base64-encoded annotated screenshot image
    """
    try:
        # Decode base64 image
        image_data = base64.b64decode(screenshot_base64)
        img = Image.open(BytesIO(image_data))
        
        # Get actual image dimensions (may differ from passed parameters)
        actual_img_width, actual_img_height = img.size
        
        # Convert to RGB for drawing (JPEG doesn't support transparency)
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Calculate click position in screenshot coordinates
        # IMPORTANT: The x, y coordinates passed here are in actual screen coordinates.
        # The screenshot may be resized (e.g., 720x1600) while actual screen is larger (e.g., 1080x2400).
        # We need to convert from actual screen coordinates to screenshot coordinates.
        # Use actual image dimensions for more accurate conversion
        if actual_screen_width and actual_screen_height and actual_screen_width > 0 and actual_screen_height > 0:
            # Screenshot is resized, convert from actual screen coordinates to screenshot coordinates
            # Use actual image dimensions if available, otherwise use passed screenshot dimensions
            target_width = actual_img_width if actual_img_width > 0 else screenshot_width
            target_height = actual_img_height if actual_img_height > 0 else screenshot_height
            
            scale_x = target_width / actual_screen_width
            scale_y = target_height / actual_screen_height
            click_x = int(x * scale_x)
            click_y = int(y * scale_y)
            
            # Debug output
            print(f"[ImageAnnotation] Screen coords: ({x}, {y}) -> Screenshot coords: ({click_x}, {click_y})")
            print(f"[ImageAnnotation] Screen size: {actual_screen_width}x{actual_screen_height}, Screenshot size: {target_width}x{target_height}, Scale: {scale_x:.3f}x{scale_y:.3f}")
        else:
            # Screenshot is not resized, coordinates should match
            # But if they don't match, we need to handle it
            # For safety, if coordinates exceed screenshot dimensions, scale them
            target_width = actual_img_width if actual_img_width > 0 else screenshot_width
            target_height = actual_img_height if actual_img_height > 0 else screenshot_height
            
            if x > target_width or y > target_height:
                # Coordinates are larger than screenshot, likely need scaling
                if target_width > 0 and target_height > 0:
                    # Assume proportional scaling
                    scale_x = target_width / max(x, target_width)
                    scale_y = target_height / max(y, target_height)
                    click_x = int(x * scale_x)
                    click_y = int(y * scale_y)
                    print(f"[ImageAnnotation] Scaled coords: ({x}, {y}) -> ({click_x}, {click_y})")
                else:
                    click_x = x
                    click_y = y
            else:
                # Coordinates are within screenshot dimensions, use directly
                click_x = x
                click_y = y
        
        # Ensure coordinates are within image bounds (use actual image dimensions)
        actual_img_width, actual_img_height = img.size
        click_x = max(0, min(click_x, actual_img_width - 1))
        click_y = max(0, min(click_y, actual_img_height - 1))
        
        # Create a drawing context
        draw = ImageDraw.Draw(img)
        
        # Draw a circle at the click position
        # Outer circle (red, solid)
        circle_radius = 20
        bbox = (
            click_x - circle_radius,
            click_y - circle_radius,
            click_x + circle_radius,
            click_y + circle_radius
        )
        draw.ellipse(bbox, fill=(255, 0, 0), outline=(255, 0, 0), width=3)
        
        # Inner circle (white, solid)
        inner_radius = 8
        inner_bbox = (
            click_x - inner_radius,
            click_y - inner_radius,
            click_x + inner_radius,
            click_y + inner_radius
        )
        draw.ellipse(inner_bbox, fill=(255, 255, 255), outline=(255, 255, 255))
        
        # Draw crosshair lines for better visibility
        line_length = 30
        # Horizontal line
        draw.line(
            [(click_x - line_length, click_y), (click_x + line_length, click_y)],
            fill=(255, 0, 0),
            width=2
        )
        # Vertical line
        draw.line(
            [(click_x, click_y - line_length), (click_x, click_y + line_length)],
            fill=(255, 0, 0),
            width=2
        )
        
        # Save annotated image to base64
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        annotated_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return annotated_base64
    except Exception as e:
        print(f"Error annotating click position: {e}")
        # Return original screenshot if annotation fails
        return screenshot_base64

