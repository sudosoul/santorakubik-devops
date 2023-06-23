# Connecting to VPN
1. Download the VPN `client configuration`: https://us-east-2.console.aws.amazon.com/vpc/home?region=us-east-2#ClientVPNEndpoints:
2. Open the `client configuration` file, and add the following entries to it:
```
<cert>
    $CERT
</cert>
<key>
    $KEY
</key>
```
Replace the `$CERT` and `$KEY` values with the client certificate data, which can be accessed via the following SSM paths:
1. `/org/vpn/client_public_key` | https://us-east-2.console.aws.amazon.com/systems-manager/parameters/org/vpn/client_public_key/description?region=us-east-2&tab=Table
2. `/org/vpn/client_private_key` | https://us-east-2.console.aws.amazon.com/systems-manager/parameters/org/vpn/client_private_key/description?region=us-east-2&tab=Table

3. Add this newly updated `client configuration` (.ovpn) file to the AWS VPN Client app as a new profile, and you should now be able to connect.

# Changing the Client Certificate
1. If you need to revoke acces to the VPN, you should generate a new client certificate.
2. Follow the instructions here on using the EasyRSA tool to generate a new `CA` and `client` certificate:
```
cd certs
git clone https://github.com/OpenVPN/easy-rsa.git
cd easy-rsa/easyrsa3
./easyrsa init-pki
./easyrsa build-ca nopass
./easyrsa build-client-full client.vpn.colerange.us nopass
```
Link: https://docs.aws.amazon.com/vpn/latest/clientvpn-admin/mutual.html
3. Move the resulting files to this location:
```
mv pki/ca.crt ../../
mv pki/issued/client.vpn.colerange.us.crt ../../
mv pki/private/client.vpn.colerange.us.key ../../

# then delete the easy-rsa package
cd ../../
rm -rf easy-rsa
```
4. You should just have 3 files in the `certs` directory:
```
ca.crt
client.vpn.colerange.us.crt
client.vpn.colerange.us.key
```
5. Pulumi will automatically delete the Private key file `./certs/client.vpn.colerange.us.key` once it has updated the VPN & SSM to use the new private key.