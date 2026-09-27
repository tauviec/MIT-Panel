<?php

class mitApi {
    private $MIT_KEY   = "j7GQhzNcBV4KU9QKYPXvtjSzCcmfkc0e";
    private $MIT_PANEL = "http://127.0.0.1:7200";

    public function __construct($mit_panel = null, $mit_key = null) {
        if ($mit_panel) {
            $this->MIT_PANEL = $mit_panel;
        }

        if ($mit_key) {
            $this->MIT_KEY = $mit_key;
        }
    }

    private function httpPostCookie($url, $data, $timeout = 60) {
        $cookie_file = './' . md5($this->MIT_PANEL) . '.cookie';
        if (!file_exists($cookie_file)) {
            $fp = fopen($cookie_file, 'w+');
            fclose($fp);
        }

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
        curl_setopt($ch, CURLOPT_COOKIEJAR, $cookie_file);
        curl_setopt($ch, CURLOPT_COOKIEFILE, $cookie_file);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        curl_setopt($ch, CURLOPT_HEADER, 0);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        $output = curl_exec($ch);
        curl_close($ch);
        return $output;
    }

    private function getKeyData() {
        $now_time   = time();
        $ready_data = array(
            'request_token' => md5($now_time . '' . md5($this->MIT_KEY)),
            'request_time'  => $now_time,
        );
        return $ready_data;
    }

    public function getLogsList() {
        $url = $this->MIT_PANEL . '/api/firewall/get_log_list';

        $post_data          = $this->getKeyData();
        $post_data['p']     = '1';
        $post_data['limit'] = 10;

        $result = $this->httpPostCookie($url, $post_data);

        $data = json_decode($result, true);
        return $data;
    }

}

$api = new mitApi();
$rdata = $api->getLogsList();

// var_dump($rdata);
echo json_encode($rdata);

?>
