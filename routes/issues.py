from flask import Blueprint, request, jsonify, current_app
import os
import json
import time
from datetime import datetime

bp = Blueprint('issues', __name__, url_prefix='/api/issues')

# Define the storage path for issues
ISSUES_FILE = 'data/issues.json'

# Ensure the data directory exists
os.makedirs(os.path.dirname(ISSUES_FILE), exist_ok=True)

# Issue status enum
class IssueStatus:
    PENDING = 'pending'
    SUBMITTED = 'submitted'
    FAILED = 'failed'

def load_issues():
    """Load issues from the issues file"""
    try:
        if os.path.exists(ISSUES_FILE):
            with open(ISSUES_FILE, 'r') as f:
                issues = json.load(f)
                return issues
        return []
    except Exception as e:
        current_app.logger.error(f"Error loading issues: {str(e)}")
        return []

def save_issues(issues):
    """Save issues to the issues file"""
    try:
        os.makedirs(os.path.dirname(ISSUES_FILE), exist_ok=True)
        with open(ISSUES_FILE, 'w') as f:
            json.dump(issues, f, indent=2)
        return True
    except Exception as e:
        current_app.logger.error(f"Error saving issues: {str(e)}")
        return False

@bp.route('/', methods=['GET'])
def get_issues():
    """Get all issues"""
    issues = load_issues()
    return jsonify(issues)

@bp.route('/', methods=['POST'])
def create_issue():
    """Create a new issue"""
    try:
        data = request.json
        
        # Validate required fields
        if not data or not data.get('title') or not data.get('description'):
            return jsonify({"error": "Missing required fields"}), 400
        
        issues = load_issues()
        
        # Create new issue
        new_issue = {
            'id': str(int(time.time() * 1000)),  # Unique ID based on timestamp
            'title': data.get('title'),
            'description': data.get('description'),
            'type': data.get('type', 'bug'),
            'timestamp': datetime.now().isoformat(),
            'status': IssueStatus.PENDING,
            'retries': 0
        }
        
        issues.append(new_issue)
        
        if save_issues(issues):
            return jsonify(new_issue), 201
        else:
            return jsonify({"error": "Failed to save issue"}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error creating issue: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/<issue_id>', methods=['PUT'])
def update_issue(issue_id):
    """Update an issue's status"""
    try:
        data = request.json
        issues = load_issues()
        
        # Find the issue
        issue = next((i for i in issues if i['id'] == issue_id), None)
        
        if not issue:
            return jsonify({"error": "Issue not found"}), 404
            
        # Update issue status
        if 'status' in data:
            issue['status'] = data['status']
        
        # Update other fields if provided
        if 'retries' in data:
            issue['retries'] = data['retries']
        
        if save_issues(issues):
            return jsonify(issue)
        else:
            return jsonify({"error": "Failed to save issue"}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error updating issue: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/<issue_id>', methods=['DELETE'])
def delete_issue(issue_id):
    """Delete an issue"""
    try:
        issues = load_issues()
        
        # Remove the issue
        new_issues = [i for i in issues if i['id'] != issue_id]
        
        if len(new_issues) == len(issues):
            return jsonify({"error": "Issue not found"}), 404
            
        if save_issues(new_issues):
            return jsonify({"success": True, "message": "Issue deleted"})
        else:
            return jsonify({"error": "Failed to save issues"}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error deleting issue: {str(e)}")
        return jsonify({"error": str(e)}), 500 