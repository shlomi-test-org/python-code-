(ns insecure-crypto-example
  (:import (javax.crypto Cipher KeyGenerator SecretKey)
           (java.security MessageDigest Security)
           (javax.net.ssl SSLContext TrustManager X509TrustManager)
           [java.security.cert X509Certificate]))

(defn weak-hash-function [input]
  (let [md (MessageDigest/getInstance "MD5")]
    (.update md (.getBytes input))
    (.digest md)))

(defn deprecated-3des-encryption [data]
  (let [keygen (KeyGenerator/getInstance "DESede")
        cipher (Cipher/getInstance "DESede")]
    (.init keygen 112)  ; Generate a 112-bit key for Triple DES
    (let [key (SecretKey. (.generateKey keygen))]
      (.init cipher Cipher/ENCRYPT_MODE key)
      (.doFinal cipher (.getBytes "UTF-8" data)))))

(defn insecure-ssl-context []
  (let [ssl-context (SSLContext/getInstance "TLS")]
    (do
      (.init ssl-context nil (into-array TrustManager [(reify X509TrustManager
                                                       (checkClientTrusted [this chain authType])
                                                       (checkServerTrusted [this chain authType])
                                                       (getAcceptedIssuers [this] nil))]) nil)
      ssl-context)))

(defn -main [& args]
  (println "Weak MD5 hash:" (weak-hash-function "example"))
  (println "3DES encrypted data:" (deprecated-3des-encryption "secret data"))
  (println "Insecure SSL context created:" (insecure-ssl-context)))

