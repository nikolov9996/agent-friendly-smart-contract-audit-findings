---
id: 12606
severity: "Medium"
---

# `IsWrappedFcash` check is a gas bomb

## Description

In the `_isWrappedFCash` check, the `notionalTradeModule` check whether the component is a wrappedCash with the following logic.

```solidity
try IWrappedfCash(_fCashPosition).getDecodedID() returns(uint16 _currencyId, uint40 _maturity){
    try wrappedfCashFactory.computeAddress(_currencyId, _maturity) returns(address _computedAddress){
        return _fCashPosition == _computedAddress;
    } catch {
        return false;
    }
} catch {
    return false;
}
```

The above logic is dangerous when `_fCashPosition` do not revert on `getDecodedID` but instead give a wrong format of return value. The contract would try to decode the return value into `returns(uint16 _currencyId, uint40 _maturity)` and revert. The revert would consume whatever gas it’s provided.

[CETH](https://etherscan.io/address/0x4Ddc2D193948926D02f9B1fE9e1daa0718270ED5) is an example. There’s a fallback function in `ceth`

```solidity
function () external payable {
    requireNoError(mintInternal(msg.value), "mint failed");
}
```

As a result, calling `getDecodedID` would not revert. Instead, calling `getDecodedID` of `CETH` would consume all remaining gas. This creates so many issues. First, users would waste too much gas on a regular operation. Second, the transaction might fail if `ceth` is not the last position. Third, the wallet contract can not interact with set token with ceth as it consumes all gas.

## Proof of Concept

The following contract may fail to redeem setTokens as it consumes too much gas (with 20M gas limit).

[Test.sol](https://gist.github.com/Jonah246/fad9e489fe84a6fb8b4894d7377fd8a2)

```solidity
function test(uint256 _amount) external {
    cToken.approve(address(issueModule), uint256(-1));
    wfCash.approve(address(issueModule), uint256(-1));
    issueModule.issue(setToken, _amount, address(this));
    issueModule.redeem(setToken, _amount, address(this));
}
```

Also, we can check how much gas it consumes with the following function.

```solidity
function TestWrappedFCash(address _fCashPosition) public view returns(bool){
    if(!_fCashPosition.isContract()) {
        return false;
    }
    try IWrappedfCash(_fCashPosition).getDecodedID() returns(uint16 _currencyId, uint40 _maturity){
        try wrappedfCashFactory.computeAddress(_currencyId, _maturity) returns(address _computedAddress){
            return _fCashPosition == _computedAddress;
        } catch {
            return false;
        }
    } catch {
        return false;
    }
}
```

Test this function with `cdai` and `ceth`, we can observe that there’s huge difference of gas consumption here.

Gas used:            30376 of 130376  
Gas used:            19479394 of 19788041

## Recommendation

I recommend building a map in the notionalTradeModule and inserting the wrappeCash in the `mintFCashPosition` function.

```solidity
function addWrappedCash(uint16 _currencyId, uint40 _maturity) public {
    address computedAddress = wrappedfCashFactory.computeAddress(_currencyId, _maturity);
    wrappedFCash[computedAddress] = true;
}
```

Or we could replace the try-catch pattern with a low-level function call and check the return value’s length before decoding it.

Something like this might be a fix.

```solidity
(bool success, bytes memory returndata) = target.delegatecall(data);
if (!success || returndata.length != DECODED_ID_RETURN_LENGTH) {
    return false;
}
// abi.decode ....
```

Correct, this is an issue that I also recently ran into (after the contest had already started) when doing additional tests. My solution was to just add a fixed gas limit to the `getDecodedID` call which seemed to solve it. 

In an earlier version of the contract I had a manual mapping as suggested here, however this is not ideal since the setToken could obtain fCash positions using other SetModules (such as the general TradeModule) which would then not be registered in this mapping. 

Limiting the gas usage of these calls seems like an easier and more robust mitigation strategy. (might want to make these gas limits updateable though)

Valid but don’t think this is High Risk, `eth_estimateGas` should fail preventing most user from interacting with a ridiculous gas limit.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a gas‑intensive failure path triggered when the Notional Trade Module attempts to identify whether a supplied fCash position represents a wrapped cash token. The module calls the external contract’s getDecodedID function inside a nested try‑catch block, expecting the call to either revert on a non‑wrapped contract or to return a correctly encoded pair of a currency identifier and a maturity timestamp. When the target contract, such as CETH, implements getDecodedID without reverting but instead returns data that does not match the expected ABI – for example, returning a single uint256 or executing arbitrary logic – the Solidity decoder attempts to unpack the response into a uint16 and a uint40. This mismatched decoding causes an automatic revert, which consumes all remaining gas supplied to the transaction. Because the revert occurs inside the try‑catch, the outer logic cannot recover, so the entire operation aborts after exhausting the gas limit.

The root cause is the reliance on ABI‑conforming returns from an untrusted external contract without first validating the size or format of the returned calldata. The try‑catch construct assumes that a malformed response will trigger a revert, but Solidity’s low‑level decoder will revert internally when the calldata length does not match the expected static tuple, leading to a silent gas bomb. This behavior is especially problematic for tokens that implement a fallback payable function that forwards calls to other logic without reverting, such as CETH’s payable fallback that silently consumes gas.

An attacker or merely a mis‑behaving token can exploit this by providing a contract that implements getDecodedID with a non‑standard signature or by deploying a wrapper that returns a malformed payload. When a user or a wallet contract interacts with the Notional system and includes such a token among its positions, the gas consumption of a regular operation like issue or redeem can skyrocket, often approaching or exceeding typical block gas limits. The impact is that legitimate users waste large amounts of gas, experience transaction failures, and may be unable to redeem or interact with SetTokens that contain the offending wrapped cash token. From a user perspective, the UI may show a transaction that started normally but then stalls, reports "out of gas", or simply disappears, leaving the user confused as no funds are transferred and the transaction reverts.

The issue surfaces whenever the Notional Trade Module processes a list of fCash positions that includes a contract which does not adhere to the expected getDecodedID interface. It is most noticeable when the offending contract is not the last element in the list, because earlier gas‑heavy reverts prevent later logic from executing. The vulnerability was discovered during a manual audit and reproduced with a test contract that calls getDecodedID on CETH, revealing a stark contrast in gas usage between a correctly formatted token (≈30 k gas) and the malformed token (≈19.5 M gas). The problem can be hard to notice because the external call does not revert with an explicit error; instead, the transaction simply runs out of gas, which may be attributed to other factors.

To remediate the issue, the module should avoid trusting the ABI shape of external calls without verification. A recommended fix is to replace the high‑level try‑catch with a low‑level call that checks the returned calldata length before attempting to decode, ensuring that only correctly sized responses are processed. Alternatively, maintaining an explicit whitelist mapping of known wrapped cash addresses inserted at mint time can bypass the need for dynamic decoding, though this approach must be synchronized with all modules that can introduce new positions. Adding a fixed gas stipend to the getDecodedID call or imposing an adjustable gas limit for such external calls can also mitigate the risk by preventing unlimited gas consumption. In any case, the solution should enforce validation of external contract responses before decoding to eliminate the gas bomb scenario.
