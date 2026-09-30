---
id: 20163
severity: "High"
---

# LibMuon Signature hash collision

## Description

In LibMuon, all signatures do not distinguish between type prefixes, and abi.encodePacked is used when calculating the hash. Cause when abi.encodePacked, if there is a dynamic array, different structures but the same hash value may be obtained. Due to conflicting hash values, signatures can be substituted for each other, making malicious use of illegal signatures possible.
The following two methods are examples:
1. verifyPrices:
```solidity
function verifyPrices(PriceSig memory priceSig, address partyA) internal view {
    MuonStorage.Layout storage muonLayout = MuonStorage.layout();
    require(priceSig.prices.length == priceSig.symbolIds.length, "LibMuon: Invalid length");
    bytes32 hash = keccak256(
        abi.encodePacked(
            muonLayout.muonAppId,
            priceSig.reqId,
            address(this),
            partyA,
            priceSig.upnl,
            priceSig.totalUnrealizedLoss,
            priceSig.symbolIds,
            priceSig.prices,
            priceSig.timestamp,
            getChainId()
        )
    );
    verifyTSSAndGateway(hash, priceSig.sigs, priceSig.gatewaySignature);
}
```
2. verifyPartyAUpnlAndPrice
```solidity
function verifyPartyAUpnlAndPrice(
    SingleUpnlAndPriceSig memory upnlSig,
    address partyA,
    uint256 symbolId
) internal view {
    MuonStorage.Layout storage muonLayout = MuonStorage.layout();
    require(
        block.timestamp <= upnlSig.timestamp + muonLayout.upnlValidTime,
        "LibMuon: Expired signature"
    );
    bytes32 hash = keccak256(
        abi.encodePacked(
            muonLayout.muonAppId,
            upnlSig.reqId,
            address(this),
            partyA,
            AccountStorage.layout().partyANonces[partyA],
            upnlSig.upnl,
            symbolId,
            upnlSig.price,
            upnlSig.timestamp,
            getChainId()
        )
    );
    verifyTSSAndGateway(hash, upnlSig.sigs, upnlSig.gatewaySignature);
}
```
We exclude the same common part (muonAppId/reqId/address(this)/timestamp/getChainId()).
Through the following simplified test code, although the structure is different, the hash value is the same at that time:
```solidity
function test() external {
    address verifyPrices_partyA = address(0x1);
    int256 verifyPrices_upnl = 100;
    int256 verifyPrices_totalUnrealizedLoss = 100;
    uint256[] memory verifyPrices_symbolIds = new uint256[](1);
    verifyPrices_symbolIds[0] = 1;
    uint256[] memory verifyPrices_prices = new uint256[](1);
    verifyPrices_prices[0] = 1000;
    bytes32 verifyPrices = keccak256(abi.encodePacked(
        verifyPrices_partyA,
        verifyPrices_upnl,
        verifyPrices_totalUnrealizedLoss,
        verifyPrices_symbolIds,
        verifyPrices_prices
    ));
    address verifyPartyAUpnlAndPrice_partyA = verifyPrices_partyA;
    int256 verifyPartyAUpnlAndPrice_partyANonces = verifyPrices_upnl;
    int256 verifyPartyAUpnlAndPrice_upnl = verifyPrices_totalUnrealizedLoss;
    uint256 verifyPartyAUpnlAndPrice_symbolId = verifyPrices_symbolIds[0];
    uint256 verifyPartyAUpnlAndPrice_price = verifyPrices_prices[0];
    bytes32 verifyPartyAUpnlAndPrice = keccak256(abi.encodePacked(
        verifyPartyAUpnlAndPrice_partyA,
        verifyPartyAUpnlAndPrice_partyANonces,
        verifyPartyAUpnlAndPrice_upnl,
        verifyPartyAUpnlAndPrice_symbolId,
        verifyPartyAUpnlAndPrice_price
    ));
    console.log("verifyPrices == verifyPartyAUpnlAndPrice:", verifyPrices == verifyPartyAUpnlAndPrice);
}
```
$ forge test -vvv
Running 1 test for test/Counter.t.sol:CounterTest
[PASS] test() (gas: 4991)
Logs:
verifyPrices == verifyPartyAUpnlAndPrice: true
Test result: ok. 1 passed; 0 failed; finished in 11.27ms
From the above test example, we can see that the verifyPrices and verifyPartyAUpnlAndPrice signatures can be used interchangeably. If we get a legal verifyPartyAUpnlAndPrice, it can be used as the signature of verifyPrices(). Use partyANonces as upnl, etc.
Signatures can be reused due to hash collisions, through illegal signatures, using illegal unpl, etc.

## Proof of Concept

no poc

## Recommendation

It is recommended to add the prefix of the hash, or use api.encode. Such as:
```solidity
function verifyPrices(PriceSig memory priceSig, address partyA) internal view {
    MuonStorage.Layout storage muonLayout = MuonStorage.layout();
    require(priceSig.prices.length == priceSig.symbolIds.length, "LibMuon: Invalid length");
    bytes32 hash = keccak256(
        abi.encodePacked(
            "verifyPrices",
            muonLayout.muonAppId,
            priceSig.reqId,
            address(this),
            partyA,
            priceSig.upnl,
            priceSig.totalUnrealizedLoss,
            priceSig.symbolIds,
            priceSig.prices,
            priceSig.timestamp,
            getChainId()
        )
    );
    verifyTSSAndGateway(hash, priceSig.sigs, priceSig.gatewaySignature);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a hash‑collision weakness in the LibMuon signature scheme. The library builds the message hash with keccak256(abi.encodePacked(...)) and does not prepend any function‑specific identifier or type tag. Because abi.encodePacked concatenates the raw binary representation of each argument, different argument layouts – especially when dynamic arrays are involved – can produce exactly the same byte sequence. Consequently two distinct logical messages, such as a price‑verification payload and a profit‑and‑loss verification payload, may generate an identical hash. The root cause is the lack of a domain separator or explicit type prefix, which makes the hash ambiguous. An attacker who obtains a legitimate signature for one function (for example a SingleUpnlAndPriceSig) can reuse that signature as a valid proof for another function (such as verifyPrices) because the verifier recomputes the same hash from the forged data. Exploitation proceeds by crafting a payload whose fields are rearranged to match the byte layout of a different function, submitting the reused signature, and passing the verifyTSSAndGateway check. The impact is that the protocol can be tricked into accepting unauthorized price updates or profit‑and‑loss reports, potentially leading to incorrect accounting, unauthorized fund movements, or loss of user balances. The bug manifests whenever a signature is verified using the vulnerable hash construction – i.e., any call to verifyPrices or verifyPartyAUpnlAndPrice – and when the attacker can control at least one of the dynamic array arguments. All participants that rely on the integrity of these signatures – the protocol itself, its users, and any downstream contracts – are affected. The issue was discovered during a manual audit when the auditor wrote a small test that showed two different encodePacked calls producing the same keccak256 hash, confirming that the signatures are interchangeable. Because hash collisions are not obvious from the contract’s external behaviour, the problem can remain hidden until a crafted exploit is attempted. The bug belongs to the class of “signature domain‑separation failures” or “abi.encodePacked collision” bugs, where the message format does not uniquely identify the operation. From a user’s perspective the symptom may appear as unexpected price changes, a profit‑and‑loss value that seems to have been altered without any transaction, or a balance that suddenly moves without a visible cause – the user expects a legitimate update but receives an unauthorized one. To remediate the issue the contract should adopt a collision‑resistant message encoding: either switch to abi.encode (which includes length information) or prepend a unique string identifier for each function before hashing, thereby ensuring that each logical message maps to a distinct hash domain. This change restores the cryptographic guarantee that a signature can only be used for the exact operation it was created for, eliminating the possibility of signature reuse across different function calls.
