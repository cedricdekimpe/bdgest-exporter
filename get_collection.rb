require 'httparty'
require 'nokogiri'

LOGIN_URL = 'https://online.bdgest.com/login'
# Mimic a browser User-Agent
HEADERS = {
  'User-Agent' => 'Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0',
  'Accept' => 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8',
  'Accept-Language' => 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
  'Accept-Encoding' => 'gzip, deflate, br, zstd',
  'Referer' => 'https://online.bdgest.com/',
  'Connection' => 'keep-alive',
  'Upgrade-Insecure-Requests' => '1',
  'DNT' => '1',
  'Sec-GPC' => '1',
  'Pragma' => 'no-cache',
  'Cache-Control' => 'no-cache'
}

def fetch_csrf_token_and_cookies
  response = HTTParty.get(LOGIN_URL, headers: HEADERS)

  raise "Failed to fetch login page. HTTP Status: #{response.code}" unless response.code == 200

  # Parse the HTML to extract the CSRF token
  html = Nokogiri::HTML(response.body)
  csrf_token = html.at_css('input[name="csrf_token_bdg"]')&.attr('value')
  raise 'CSRF token not found!' unless csrf_token

  # Extract cookies
  cookies = response.headers['set-cookie']
  cookie_hash = parse_cookies(cookies)

  [csrf_token, cookie_hash]
end

def parse_cookies(raw_cookie_header)
  cookies = {}
  raw_cookie_header.split(', ').each do |cookie_pair|
    key, value = cookie_pair.split('; ').first.split('=')
    cookies[key] = value
  end
  cookies
end

filename = ARGV[0]
collection_id = ARGV[1].to_i

csrf_token, initial_cookies = fetch_csrf_token_and_cookies

payload = {
  'csrf_token_bdg' => csrf_token,
  'li1' => 'username',
  'li2' => 'password',
  'source' => '',
  'username' => ENV.fetch('BDGEST_USERNAME'),
  'password' => ENV.fetch('BDGEST_PASSWORD')
}

# Build cookie string for the login request
cookie_string = initial_cookies.map { |k, v| "#{k}=#{v}" }.join('; ')

login_headers = HEADERS.merge('Cookie' => cookie_string)
response = HTTParty.post(LOGIN_URL, headers: login_headers, body: payload)

cookies = response.request.options[:headers]['Cookie']

r3 = HTTParty.get("https://online.bdgest.com/exportation?filename=#{filename}&collection=#{collection_id}",
                  headers: { 'Cookie' => cookies })

File.open("./tmp/#{filename}", 'w') { |file| file.write(r3.response.body) }
