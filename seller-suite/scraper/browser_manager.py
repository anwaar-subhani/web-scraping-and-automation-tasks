"""Browser and proxy management"""
import os
import uuid
from . import config

def generate_unique_id():
    """Generate a unique ID for proxy extension"""
    return uuid.uuid4().int >> 64

def create_proxy_auth_extension(proxy_string, bypass_list=None):
    """
    Creates a Chrome extension for proxy authentication with a specific proxy and bypass list.
    Similar to the sample project implementation.

    :param proxy_string: Proxy in the format of host:port or host:port:username:password
    :param bypass_list: List of URLs to bypass the proxy
    :return: Path to the proxy extension directory
    """
    # Extract proxy details from the provided string
    try:
        parts = proxy_string.split(':')
        if len(parts) >= 4:
            host, port, username, password = parts[0], parts[1], parts[2], parts[3]
        else:
            host, port = parts[0], parts[1]
            username = ""
            password = ""
    except Exception as e:
        raise ValueError(f"Invalid proxy format: {proxy_string}. Expected format: host:port or host:port:username:password")

    # Convert the bypass list to a valid JSON array if provided
    bypass_list_json = '[]'
    if bypass_list:
        bypass_list_json = f'["' + '","'.join(bypass_list) + '"]'

    # Manifest file for the extension
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "storage",
            "activeTab",
            "scripting",
            "alarms",
            "tabs",
            "webRequest",
            "webRequestAuthProvider",
            "webRequestBlocking",
            "http://*/*",
            "https://*/*"
        ],
        "background": {
            "service_worker": "background.js"
        },
        "host_permissions": [
            "*://*/*"
        ]
    }
    """

    # Background script for the extension
    background_js = f"""
let currentProxy = {{
    host: "{host}",
    port: {port},
    auth: {{
        username: "{username}",
        password: "{password}"
    }}
}};

// Set the proxy settings with the bypass list
chrome.proxy.settings.set({{
    value: {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: currentProxy.host,
                port: currentProxy.port
            }},
            bypassList: {bypass_list_json}
        }}
    }},
    scope: "regular"
}}, function() {{
    console.log("Proxy set successfully.");
}});

chrome.webRequest.onAuthRequired.addListener(
    function(details) {{
        return {{
            authCredentials: {{
                username: currentProxy.auth.username,
                password: currentProxy.auth.password
            }}
        }};
    }},
    {{ urls: ["<all_urls>"] }},
    ['blocking']
);
    """

    # Create a temporary directory for the unpacked extension in current working directory inside temp folder
    unique_id = generate_unique_id()
    plugin_dir = os.path.join(os.getcwd(), "temp",
                              f"proxy_extension_{host}_{port}_{username}_{password}_{unique_id}")
    # Create the directory if it doesn't exist
    os.makedirs(plugin_dir, exist_ok=True)

    # Write manifest.json and background.js to the temp directory
    with open(os.path.join(plugin_dir, "manifest.json"), 'w') as manifest_file:
        manifest_file.write(manifest_json)

    with open(os.path.join(plugin_dir, "background.js"), 'w') as background_file:
        background_file.write(background_js)

    return plugin_dir

def get_next_proxy():
    """Get next proxy in rotation (thread-safe) - returns proxy string"""
    if not config.PROXIES_LIST:
        return None
    
    with config.proxy_lock:
        proxy = config.PROXIES_LIST[config.proxy_index % len(config.PROXIES_LIST)]
        config.proxy_index += 1
        return proxy

