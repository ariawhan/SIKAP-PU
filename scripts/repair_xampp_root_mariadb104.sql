USE mysql;

DELETE FROM global_priv
WHERE User IN ('root', 'pma')
  AND Host IN ('localhost', '127.0.0.1', '::1');

INSERT INTO global_priv (Host, User, Priv) VALUES
('localhost', 'root', '{"access":18446744073709551615,"plugin":"mysql_native_password","authentication_string":"","auth_or":[{},{"plugin":"unix_socket"}],"password_last_changed":0}'),
('127.0.0.1', 'root', '{"access":18446744073709551615,"plugin":"mysql_native_password","authentication_string":"","auth_or":[{},{"plugin":"unix_socket"}],"password_last_changed":0}'),
('::1', 'root', '{"access":18446744073709551615,"plugin":"mysql_native_password","authentication_string":"","auth_or":[{},{"plugin":"unix_socket"}],"password_last_changed":0}'),
('localhost', 'pma', '{"access":0,"plugin":"mysql_native_password","authentication_string":"","password_last_changed":0}');

FLUSH PRIVILEGES;
