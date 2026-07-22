## Authentication

#### Overview

All requests provide authentication information through the Authorization Header.

#### Authentication header structure

Authorization: SHA256 Credentials=[{Appid}](https://affiliate.shopee.com.br/open_api), Timestamp=[{Timestamp}](https://www.unixtimestamp.com/), Signature={[Calculation method:](https://affiliate.shopee.com.br/open_api/document?type=overview#calculationSection)SHA256(Credential+Timestamp+Payload+Secret}

#### Example Of Authorization Header

Authorization: SHA256 Credential=123456, Timestamp=1599999999, Signature=9bc0bd3ba6c41d98a591976bf95db97a58720a9e6d778845408765c3fafad69d.

#### Description of all parts of Authorization header

#### Signature Calculation

Before sending a request, please obtain the AppId and Secret from [here](https://affiliate.shopee.com.br/open_api). (Please keep the secret equivalent to the password, don’t disclose it.)

#### Calculation Steps

-   Get the payload of the request, payload is a request body
    
    ```
    {"query":"{\nbrandOffer{\n    nodes{\n        commissionRate\n        offerName\n    }\n}\n}"}
    ```
    
    According to GraphQL standard, the request body must be in a valid JSON format.  
    When query by string conditions we should escape double quotes first. Like this,  
    {"query":"{conversionReport(purchaseTimeStart: 1600621200, purchaseTimeEnd: 1601225999, scrollId: "some characters"){...}}
-   Get the current [timestamp](https://www.unixtimestamp.com/)
-   Construct a signature factor. Compose a string with AppId+Timestamp+Payload+Secret
-   Perform the SHA256 algorithm on the signature factor, signature=SHA256(Credential+Timestamp+Payload+Secret) to get the signature (lowercase hexadecimal)
-   Generate Authorization header: SHA256 Credential=${AppId}, Timestamp=${Timestamp}, Signature=${signature}

Example

Hypothesis AppId=123456, Secret=demo,  
Current time=2020-01-01 00:00:00 UTC+0, Timestamp=1577836800,  
Please send payload as

```
{"query":"{\nbrandOffer{\n    nodes{\n        commissionRate\n        offerName\n    }\n}\n}"}
```

-   Get the payload of the request
-   Get the current timestamp
-   Construct a signature factor: AppId+Timestamp+Payload+Sercet  
    
-   Calculate the signature  
    signature=sha256(factor)，result should be dc88d72feea70c80c52c3399751a7d34966763f51a7f056aa070a5e9df645412
-   Generate Authorization header  
    Authorization:SHA256 Credential=123456,  
    Timestamp=1577836800,Signature=dc88d72feea70c80c52c3399751a7d34966763f51a7f056aa070a5e9df645412