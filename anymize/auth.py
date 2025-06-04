import requests
import logging
import random
import string
from flask import session
from datetime import datetime, timedelta
from config_shared import (
    AUTH_EMAIL_WEBHOOK_URL,
    USER_LIST_ENDPOINT,
    USER_UPDATE_ENDPOINT,
    USER_ENDPOINT,
    HEADERS
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_verification_code():
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))


def send_email_verification(email):
    """
    Send verification request to n8n webhook. 
    n8n will generate the code and store it in NocoDB.
    
    Args:
        email: User's email address
        
    Returns:
        bool: True if webhook call successful, False otherwise
    """
    try:
        # Send email request to n8n webhook
        webhook_data = {
            'email': email
        }
        
        logger.info(f"Sending email verification request for {email}")
        
        webhook_response = requests.post(
            AUTH_EMAIL_WEBHOOK_URL,
            json=webhook_data
        )
        
        if webhook_response.status_code == 200:
            # Store email in session for verification
            session['auth_email'] = email
            session['auth_timestamp'] = datetime.now().isoformat()
            logger.info(f"Email verification request sent successfully to {email}")
            return True
        else:
            logger.error(f"Failed to send email webhook: {webhook_response.status_code} - {webhook_response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error in send_email_verification: {str(e)}")
        return False


def get_user_by_email(email):
    """
    Get user from NocoDB by email.
    
    Args:
        email: User's email address
        
    Returns:
        dict: User data or None if not found
    """
    try:
        # Use filter to find user by email
        params = {
            'where': f"(email,eq,{email})"
        }
        
        response = requests.get(
            USER_LIST_ENDPOINT,
            params=params,
            headers=HEADERS
        )
        
        if response.status_code == 200:
            data = response.json()
            users = data.get('list', [])
            
            if users:
                return users[0]  # Return first matching user
                
        return None
        
    except Exception as e:
        logger.error(f"Error getting user by email: {str(e)}")
        return None


def verify_code(email, code):
    """
    Verify the provided code against the one stored in NocoDB.
    
    Args:
        email: User's email address
        code: 6-digit verification code
        
    Returns:
        bool: True if code matches, False otherwise
    """
    try:
        # Remove any whitespace from the code
        code = code.strip()
        
        # Get user from database - this always fetches fresh data
        logger.info(f"Fetching user data for verification: {email}")
        user = get_user_by_email(email)
        
        if not user:
            logger.error(f"No user found for email: {email}")
            return False
        
        # IMPORTANT: The 'code' field in NocoDB is stored as a number
        # This means leading zeros are lost (e.g., 012345 becomes 12345)
        # We need to handle this by padding with zeros
        stored_code = user.get('code', '')
        
        # Convert to string and pad with zeros to ensure 6 digits
        if isinstance(stored_code, (int, float)):
            stored_code = str(int(stored_code)).zfill(6)
        else:
            stored_code = str(stored_code).zfill(6)
            
        logger.info(f"Comparing codes for {email} - Input: {code}, Stored (padded): {stored_code}")
        
        if stored_code == code:
            # Store user info in session
            session['authenticated'] = True  # IMPORTANT: Set authenticated flag
            session['user_email'] = email
            session['user_id'] = user.get('Id')
            
            # Set session timestamps for activity tracking
            now = datetime.now()
            session['login_time'] = now.isoformat()
            session['last_activity'] = now.isoformat()
            
            # Always use permanent session but rely on inactivity timeout
            session.permanent = True
            
            # Clear temporary auth session data
            session.pop('auth_email', None)
            session.pop('auth_timestamp', None)
            
            logger.info(f"User {email} successfully authenticated with code {code[:2]}****")
            return True
        else:
            logger.warning(f"Invalid code for user {email} - Input: {code}, Expected: {stored_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error in verify_code: {str(e)}", exc_info=True)
        return False


def is_authenticated():
    """
    Check if user is authenticated.
    
    Returns:
        bool: True if authenticated, False otherwise
    """
    return session.get('authenticated', False)


def get_current_user():
    """
    Get current authenticated user data.
    
    Returns:
        dict: User data or None if not authenticated
    """
    if not is_authenticated():
        return None
        
    user_email = session.get('user_email')
    if user_email:
        return get_user_by_email(user_email)
        
    return None


def logout():
    """Clear authentication session."""
    session.pop('authenticated', None)
    session.pop('user_email', None)
    session.pop('user_id', None)
    session.pop('auth_email', None)
    session.pop('auth_timestamp', None)
    session.pop('login_time', None)
    session.pop('last_activity', None)
