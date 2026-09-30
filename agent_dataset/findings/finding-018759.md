---
id: 18759
severity: "High"
---

# Read-only reentrancy

## Description

The current implementation is vulnerable to read-only reentrancy, especially in [Wells::removeLiquidity](https://github.com/BeanstalkFarms/Wells/blob/e5441fc78f0fd4b77a898812d0fd22cb43a0af55/src/Well.sol#L440).
The implementation does not strictly follow the [Checks-Effects-Interactions (CEI) pattern](https://fravoll.github.io/solidity-patterns/checks_effects_interactions.html) as it is setting the new reserve values after sending out the tokens. This is not an immediate risk to the protocol itself due to the `nonReentrant` modifier, but this is still vulnerable to [read-only reentrancy](https://chainsecurity.com/curve-lp-oracle-manipulation-post-mortem/).

Malicious attackers and unsuspecting ecosystem participants can deploy Wells with ERC-777 tokens (which have a callback that can take control) and exploit this vulnerability. This will lead to critical vulnerabilities given that the Wells are to be extended with price functions as defined by pumps - third-party protocols that integrate these on-chain oracles will be at risk.

Pumps are updated before token transfers; however, reserves are only set after. Therefore, pump functions will likely be incorrect on a re-entrant read-only call if `IWell(well).getReserves()` is called but reserves have not been correctly updated. The implementation of `GeoEmaAndCumSmaPump` appears not to be vulnerable, but given that each pump can choose its approach for recording a well's reserves over time, this remains a possible attack vector.

Although this is not an immediate risk to the protocol itself, read-only re-entrancy can lead to critical issues, so we evaluate the severity as HIGH.

## Proof of Concept

We wrote a test case to show the existing read-only reentrancy.

```solidity
// MockCallbackRecipient.sol

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import {console} from "forge-std/Test.sol";

contract MockCallbackRecipient {
    fallback() external payable {
        console.log("here");
        (bool success, bytes memory result) = msg.sender.call(abi.encodeWithSignature("getReserves()"));
        if (success) {
            uint256[] memory reserves = abi.decode(result, (uint256[]));
            console.log("read-only-reentrancy beforeTokenTransfer reserves[0]: %s", reserves[0]);
            console.log("read-only-reentrancy beforeTokenTransfer reserves[1]: %s", reserves[1]);
        }
    }
}

// NOTE: Put in Exploit.t.sol
function test_exploitReadOnlyReentrancyRemoveLiquidityCallbackToken() public {
    IERC20 callbackToken = IERC20(new MockCallbackToken("CallbackToken", "CBTKN", 18));
    MockToken(address(callbackToken)).mint(user, 1000e18);
    IERC20[] memory _tokens = new IERC20[](2);
    _tokens[0] = callbackToken;
    _tokens[1] = tokens[1];

    vm.stopPrank();
    Well well2 = Well(auger.bore("Well2", "WELL2", _tokens, wellFunction, pumps));
    approveMaxTokens(user, address(well2));

    uint[] memory amounts = new uint[](2);
    amounts[0] = 100 * 1e18;
    amounts[1] = 100 * 1e18;

    changePrank(user);
    callbackToken.approve(address(well2), type(uint).max);
    uint256 lpAmountOut = well2.addLiquidity(amounts, 0, user);

    well2.removeLiquidity(lpAmountOut, amounts, user);
}
```

The output is shown below.

```
forge test -vv --match-test test_exploitReadOnlyReentrancyRemoveLiquidityCallbackToken

[PASS] test_exploitReadOnlyReentrancyRemoveLiquidityCallbackToken() (gas: 5290876)
Logs:
  read-only-reentrancy beforeTokenTransfer reserves[0]: 0
  read-only-reentrancy beforeTokenTransfer reserves[1]: 0
  read-only-reentrancy beforeTokenTransfer reserves[0]: 100000000000000000000
  read-only-reentrancy beforeTokenTransfer reserves[1]: 100000000000000000000

Test result: ok. 1 passed; 0 failed; finished in 3.66ms
```

## Recommendation

Implement the CEI pattern in relevant functions by updating reserves before making external calls. For example, the function `Well::removeLiquidity` can be modified shown below.

```solidity
function removeLiquidity(
    uint lpAmountIn,
    uint[] calldata minTokenAmountsOut,
    address recipient
) external nonReentrant returns (uint[] memory tokenAmountsOut) {
    IERC20[] memory _tokens = tokens();
    uint[] memory reserves = _updatePumps(_tokens.length);
    uint lpTokenSupply = totalSupply();

    tokenAmountsOut = new uint[](_tokens.length);
    _burn(msg.sender, lpAmountIn);

    _setReserves(reserves); // @audit CEI pattern

    for (uint i; i < _tokens.length; ++i) {
        tokenAmountsOut[i] = (lpAmountIn * reserves[i]) / lpTokenSupply;
        require(
            tokenAmountsOut[i] >= minTokenAmountsOut[i],
            "Well: slippage"
        );
        _tokens[i].safeTransfer(recipient, tokenAmountsOut[i]);
        reserves[i] = reserves[i] - tokenAmountsOut[i];
    }

    emit RemoveLiquidity(lpAmountIn, tokenAmountsOut);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a read‑only reentrancy flaw in the removeLiquidity function of the Well contract. The function updates the internal reserve accounting only after it has transferred token amounts to the caller. Because the contract calls external token contracts (via safeTransfer) before setting the new reserve values, a malicious token that implements the ERC‑777 hooks can execute a callback during the transfer. The callback can invoke getReserves on the Well while the reserves are still reflecting the pre‑transfer state. This violates the Checks‑Effects‑Interactions pattern: the effect (updating reserves) is performed after the interaction (token transfer). The root cause is the ordering of state updates relative to external calls. An attacker can deploy a Well with a callback‑enabled token, add liquidity, and then call removeLiquidity. During the token transfer, the callback reads stale reserves and can feed them to price‑pump contracts that rely on getReserves, causing the pump to compute incorrect prices or manipulate on‑chain oracle values. From a user perspective the symptoms may include unexpected zero or dramatically altered reserve values displayed in the UI, refunds that are lower than expected, or a situation where a user expects to receive a certain amount of tokens but receives none. The impact ranges from incorrect pricing and potential loss of value for liquidity providers to broader protocol risk if downstream oracle‑dependent contracts trust the manipulated price data. The issue was discovered during a security audit by Cyfrin, which added a test harness that deployed a mock ERC‑777 token with a fallback that called getReserves, demonstrating that the reserves read as zero before the transfer and as the full amount after, confirming the re‑entrancy window. Because the re‑entrancy is read‑only, it does not revert the transaction and therefore can be subtle and hard to notice in normal operation. The vulnerability belongs to the class of read‑only re‑entrancy bugs where state is read before it is correctly updated, breaking the Checks‑Effects‑Interactions pattern. The recommended mitigation is to move the reserve update before any external token transfer, i.e., follow the Checks‑Effects‑Interactions pattern, ensuring that getReserves always returns the post‑transfer state. Updating reserves first eliminates the window where a callback can observe stale data, thereby protecting price pumps and oracle calculations.
