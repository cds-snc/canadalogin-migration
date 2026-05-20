<?php

declare(strict_types=1);

function env_value(string $key, string $default = ''): string
{
    $value = getenv($key);
    return $value === false ? $default : $value;
}

function h(?string $value): string
{
    return htmlspecialchars($value ?? '', ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function first_xpath_text(DOMXPath $xpath, string $query): string
{
    $nodes = $xpath->query($query);
    if ($nodes === false || $nodes->length === 0) {
        return '';
    }
    return trim($nodes->item(0)?->textContent ?? '');
}

function first_xpath_attr(DOMXPath $xpath, string $query, string $attribute): string
{
    $nodes = $xpath->query($query);
    if ($nodes === false || $nodes->length === 0) {
        return '';
    }
    $node = $nodes->item(0);
    return $node instanceof DOMElement ? trim($node->getAttribute($attribute)) : '';
}

function decode_saml_request(string $encoded): array
{
    $decoded = base64_decode($encoded, true);
    if ($decoded === false) {
        return ['xml' => '', 'error' => 'SAMLRequest is not valid base64'];
    }

    $inflated = @gzinflate($decoded);
    if ($inflated === false) {
        $inflated = @gzuncompress($decoded);
    }
    if ($inflated === false) {
        $inflated = @gzdecode($decoded);
    }
    if ($inflated === false) {
        return ['xml' => '', 'error' => 'SAMLRequest could not be inflated'];
    }

    return ['xml' => $inflated, 'error' => ''];
}

function parse_saml_request_details(string $xml): array
{
    $details = [
        'request_id' => '',
        'issuer' => '',
        'destination' => '',
        'acs_url' => '',
        'nameid_format' => '',
        'requested_context' => '',
    ];

    if ($xml === '' || !class_exists('DOMDocument')) {
        return $details;
    }

    $previous = libxml_use_internal_errors(true);
    $dom = new DOMDocument();
    $loaded = $dom->loadXML($xml, LIBXML_NONET);
    libxml_clear_errors();
    libxml_use_internal_errors($previous);

    if (!$loaded) {
        return $details;
    }

    $xpath = new DOMXPath($dom);
    $xpath->registerNamespace('samlp', 'urn:oasis:names:tc:SAML:2.0:protocol');
    $xpath->registerNamespace('saml', 'urn:oasis:names:tc:SAML:2.0:assertion');

    $details['request_id'] = first_xpath_attr($xpath, '/*[local-name()="AuthnRequest"]', 'ID');
    $details['destination'] = first_xpath_attr($xpath, '/*[local-name()="AuthnRequest"]', 'Destination');
    $details['acs_url'] = first_xpath_attr($xpath, '/*[local-name()="AuthnRequest"]', 'AssertionConsumerServiceURL');
    $details['issuer'] = first_xpath_text($xpath, '/*[local-name()="AuthnRequest"]/saml:Issuer');
    $details['nameid_format'] = first_xpath_attr($xpath, '//samlp:NameIDPolicy', 'Format');
    $details['requested_context'] = first_xpath_text($xpath, '//samlp:RequestedAuthnContext/saml:AuthnContextClassRef');

    return $details;
}

$providerName = env_value('SIMULATOR_PROVIDER_NAME', env_value('IDP_ENTITY_ID', 'SAML IdP'));
$providerKey = env_value('SIMULATOR_PROVIDER_KEY', '');
$displayName = env_value('SIMULATOR_DISPLAY_NAME', $providerName . ' simulator');
$username = env_value('IDP_USER_NAME', 'simulated-user');
$password = env_value('IDP_USER_PASSWORD', 'simulated-password');
$nameId = env_value('IDP_USER_UID', $username);
$entityId = env_value('IDP_ENTITY_ID', '');
$loa = env_value('SIMULATOR_LOA', 'urn:gc-ca:cyber-auth:assurance:loa2');
$credentialProvider = env_value('SIMULATOR_CREDENTIAL_SERVICE_PROVIDER', $providerName);
$ssoPath = env_value('SIMULATOR_SSO_PATH', '/sso/module.php/saml/idp/singleSignOnService');
$samlRequest = $_GET['SAMLRequest'] ?? '';
$relayState = $_GET['RelayState'] ?? '';
$sigAlg = $_GET['SigAlg'] ?? '';
$signature = $_GET['Signature'] ?? '';
$decoded = is_string($samlRequest) && $samlRequest !== ''
    ? decode_saml_request($samlRequest)
    : ['xml' => '', 'error' => 'No SAMLRequest was provided'];
$requestDetails = parse_saml_request_details($decoded['xml']);
$canContinue = is_string($samlRequest) && $samlRequest !== '';
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= h($displayName) ?></title>
  <style>
    :root {
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.45;
      color: #1b1b1b;
      background: #f7f7f7;
    }

    body {
      margin: 0;
    }

    header {
      background: #26374a;
      color: #fff;
      padding: 18px 24px;
      border-bottom: 4px solid #af3c43;
    }

    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 28px 18px 48px;
    }

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }

    h2 {
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }

    .summary {
      margin: 0 0 24px;
      font-size: 16px;
    }

    .grid {
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }

    .panel {
      background: #fff;
      border: 1px solid #d6d9dd;
      border-radius: 4px;
      padding: 18px;
    }

    dl {
      margin: 0;
      display: grid;
      gap: 10px;
    }

    dt {
      font-weight: 700;
      color: #333;
    }

    dd {
      margin: 2px 0 0;
      overflow-wrap: anywhere;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 14px;
    }

    .notice {
      margin: 18px 0;
      padding: 14px 16px;
      border-left: 5px solid #f90;
      background: #fff4d6;
    }

    .actions {
      margin-top: 22px;
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }

    button {
      border: 0;
      border-radius: 4px;
      background: #26374a;
      color: #fff;
      padding: 12px 18px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
    }

    button:focus {
      outline: 3px solid #ffbf47;
      outline-offset: 2px;
    }

    button:disabled {
      background: #777;
      cursor: not-allowed;
    }

    details {
      margin-top: 18px;
      background: #fff;
      border: 1px solid #d6d9dd;
      border-radius: 4px;
      padding: 14px 16px;
    }

    summary {
      cursor: pointer;
      font-weight: 700;
    }

    textarea {
      width: 100%;
      min-height: 220px;
      margin-top: 12px;
      box-sizing: border-box;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }
  </style>
</head>
<body>
  <header>
    <h1><?= h($displayName) ?></h1>
  </header>

  <main>
    <p class="summary">
      This local-only page pauses the SAML flow so you can inspect the simulated provider and request before continuing to the signed SAML response.
    </p>

    <?php if ($decoded['error'] !== ''): ?>
      <div class="notice"><?= h($decoded['error']) ?></div>
    <?php endif; ?>

    <div class="grid">
      <section class="panel" aria-labelledby="fake-account-heading">
        <h2 id="fake-account-heading">Fake account</h2>
        <dl>
          <div>
            <dt>Provider</dt>
            <dd><?= h($providerName) ?><?= $providerKey !== '' ? ' (' . h($providerKey) . ')' : '' ?></dd>
          </div>
          <div>
            <dt>Username</dt>
            <dd><?= h($username) ?></dd>
          </div>
          <div>
            <dt>Password</dt>
            <dd><?= h($password) ?></dd>
          </div>
          <div>
            <dt>Persistent NameID / legacy PAI</dt>
            <dd><?= h($nameId) ?></dd>
          </div>
          <div>
            <dt>Credential service provider</dt>
            <dd><?= h($credentialProvider) ?></dd>
          </div>
          <div>
            <dt>Assurance</dt>
            <dd><?= h($loa) ?></dd>
          </div>
        </dl>
      </section>

      <section class="panel" aria-labelledby="saml-request-heading">
        <h2 id="saml-request-heading">SAML request</h2>
        <dl>
          <div>
            <dt>IdP entity ID</dt>
            <dd><?= h($entityId) ?></dd>
          </div>
          <div>
            <dt>Request ID</dt>
            <dd><?= h($requestDetails['request_id']) ?></dd>
          </div>
          <div>
            <dt>SP issuer</dt>
            <dd><?= h($requestDetails['issuer']) ?></dd>
          </div>
          <div>
            <dt>Destination</dt>
            <dd><?= h($requestDetails['destination']) ?></dd>
          </div>
          <div>
            <dt>ACS URL</dt>
            <dd><?= h($requestDetails['acs_url']) ?></dd>
          </div>
          <div>
            <dt>NameID format</dt>
            <dd><?= h($requestDetails['nameid_format']) ?></dd>
          </div>
          <div>
            <dt>Requested context</dt>
            <dd><?= h($requestDetails['requested_context']) ?></dd>
          </div>
        </dl>
      </section>
    </div>

    <form class="actions" method="get" action="<?= h($ssoPath) ?>">
      <input type="hidden" name="SAMLRequest" value="<?= h(is_string($samlRequest) ? $samlRequest : '') ?>">
      <?php if (is_string($relayState) && $relayState !== ''): ?>
        <input type="hidden" name="RelayState" value="<?= h($relayState) ?>">
      <?php endif; ?>
      <?php if (is_string($sigAlg) && $sigAlg !== ''): ?>
        <input type="hidden" name="SigAlg" value="<?= h($sigAlg) ?>">
      <?php endif; ?>
      <?php if (is_string($signature) && $signature !== ''): ?>
        <input type="hidden" name="Signature" value="<?= h($signature) ?>">
      <?php endif; ?>
      <button type="submit"<?= $canContinue ? '' : ' disabled' ?>>Continue as simulated <?= h($providerName) ?> user</button>
    </form>

    <details>
      <summary>Decoded SAML AuthnRequest XML</summary>
      <textarea readonly><?= h($decoded['xml']) ?></textarea>
    </details>
  </main>
</body>
</html>
