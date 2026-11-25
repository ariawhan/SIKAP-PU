$addresses = [Net.Dns]::GetHostAddresses([Net.Dns]::GetHostName())

foreach ($address in $addresses) {
    if (
        $address.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork -and
        $address.IPAddressToString -notlike "127.*" -and
        $address.IPAddressToString -notlike "169.254.*" -and
        $address.IPAddressToString -notlike "192.168.56.*"
    ) {
        Write-Output $address.IPAddressToString
        exit 0
    }
}

exit 1
