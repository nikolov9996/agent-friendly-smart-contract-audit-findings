---
id: 19452
severity: "High"
---

# Lenders can escape the blacklisting of their accounts because they can move their MarketTokens to different accounts and gain the `WithdrawOnly` Role on any account they want

## Description

Lenders can escape the sanctioning of their account in any market.

## Proof of Concept

Before diving into the details of how the lenders can escape the sanctioning of their account, first, let’s analyze how a lender can be excised from a Market:

  * When someone calls `nukeFromOrbit` within that market while flagged as sanctioned by the Chainanalysis oracle.
  * When the lender invokes `executeWithdrawal` while flagged as sanctioned by the Chainalysis oracle

In either of the two options, the execution flow calls the [`Sentinel::isSanctioned()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatSanctionsSentinel.sol#L39-L43) to verify if the account(lender) is sanctioned by the borrower of the market

  * By analyzing the [`Sentinel::isSanctioned()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatSanctionsSentinel.sol#L39-L43), it can be noted that the lender’s account must have been sanctioned in the Oracle first before the account is finally sanction in a Market.

**WildcatSanctionsSentinel.sol**
```solidity
      function isSanctioned(address borrower, address account) public view override returns (bool) {
        //@audit-info => sanctionOverrides[borrower][account] must be false <==> sanction must not be overridden for this function to return true!
        //@audit-info => If sanctionOverrides[borrower][account] is set to true, this function will return false, as if the account would not be sanctioned

        //@audit-info => For this function to return true, the account's sanction should have not been overridden (it's set to false), and the account must have been sanctioned in the ChainalysisSanctionsList Oracle.
        return
          !sanctionOverrides[borrower][account] &&
          IChainalysisSanctionsList(chainalysisSanctionsList).isSanctioned(account);
      }
```

Now, based on the previous explanation, we know that the lender’s account needs to be sanctioned in the Chainalysis Oracle before the [`Sentinel::isSanctioned()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatSanctionsSentinel.sol#L39-L43) is called.

This opens up the doors for lenders who realize that their account has been sanctioned in the Chainalysis Oracle to move their MarketTokens to different accounts before the lender’s account is fully blocked in the Market. You may be wondering what’s the point of transferring tokens to accounts that have not been granted any role in the Market, I’ll explain more about this shortly.

The lender transfers their MarketTokens to different accounts using the [`WildcatMarketToken::transfer()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/market/WildcatMarketToken.sol#L36-L39). As a result, the lender’s account that is sanctioned in the Chainalysis Oracle has no MarketTokens anymore; all those tokens have been moved to other accounts.

Now, at this point, anybody could call the `nukeFromOrbit()` function to fully sanction the lender’s account in a specific Market. Either way, the Lender has already moved their tokens to other accounts.

At this point, the lender’s MarketTokens were distributed among different accounts of their own. Such accounts have never interacted with the Market, so their current role is the `Null` Role.

Everything might look fine because the accounts where the tokens were sent have no permissions to interact with the Market, but there is a bug that allows lenders to gain the `WithdrawOnly` Role on any account they want, without having the consent of the borrower.

This problem is located in the [`WildcatMarketController::updateLenderAuthorization()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketController.sol#L182-L190). The reason of this problem will be explained in the below code walkthrough:

In short, the Lender will be able to set the `WithdrawOnly` Role to any account they wish. The reason is that any account that is not registered in the `_authorizedLenders` variable of the Controller will forward the value of `_isAuthorized` as false. In the [`WildMarketConfig::updateAccountAuthorization()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/market/WildcatMarketConfig.sol#L112-L126), because the value of `_isAuthorized` is false, it will end up granting the `WithdrawOnly` Role. This effectively allows any Lender to grant the `WithdrawOnly` Role to any account they want to.

**WildcatMarketController.sol**
```solidity
      //@audit-info => Anybody can call this function and pass a lender and an array of markets where the changes will be applied!
      function updateLenderAuthorization(address lender, address[] memory markets) external {
        for (uint256 i; i < markets.length; i++) {
          address market = markets[i];
          if (!_controlledMarkets.contains(market)) {
            revert NotControlledMarket();
          }
          //@audit-info => Forwards the value of the `lender` argument, and depending on the `lender` address is found in the _authorizedLenders EnumerableSet.AddressSet, will be forwarded a true or false accordingly
          //@audit => If the lender address is not found in the _authorizedLenders variable, it will forward a false to the Market::updateAccountAuthorization() function
          WildcatMarket(market).updateAccountAuthorization(lender, _authorizedLenders.contains(lender));
        }
      }
```

**EnumerableSet.sol**
```solidity
    function contains(AddressSet storage set, address value) internal view returns (bool) {
        //@audit-info => Calls the internal _contains()
        //@audit-info => If the given value is found it will return true, otherwise it will return false!
        return _contains(set._inner, bytes32(uint256(uint160(value))));
    }

    //@audit-info => The internal function will just return a true or false if the given value is in the set or not, but the tx won't be reverted!
    /**
    * @dev Returns true if the value is in the set. O(1).
    */
    function _contains(Set storage set, bytes32 value) private view returns (bool) {
        return set._indexes[value] != 0;
    }
```

**WildcatMarketConfig.sol**
```solidity
      function updateAccountAuthorization(
        address _account,
        //@audit-info => For any account that is not registered in the `_authorizedLenders` of the Controller, this flag was set as false!
        bool _isAuthorized
      ) external onlyController nonReentrant {
        MarketState memory state = _getUpdatedState();
        //@audit-info => If the accountAddress is not registered in the storage, the approval role is set to Null
        //@audit-info => If the account has been blacklisted, tx will revert!
        Account memory account = _getAccount(_account);
        if (_isAuthorized) {
          account.approval = AuthRole.DepositAndWithdraw;

        //@audit => Any account not registered in the Controller will be assigned the WithdrawOnly role.
        } else {
          account.approval = AuthRole.WithdrawOnly;
        }
        _accounts[_account] = account;
        _writeState(state);
        emit AuthorizationStatusUpdated(_account, account.approval);
      }
```

At this point, the Lender has been able to move their MarketTokens to different accounts and to grant the `WithdrawOnly` Role to all of the accounts they wish to.

Now, they can decide to exit the Market by queuing and executing some withdrawal requests from the different accounts where the MarketTokens were moved. Any of those accounts have now the `WithdrawOnly` Role and have a balance of MarketTokens, so the Lender will be able to exit the market from any of those accounts.

## Recommendation

The mitigation for this problem is very straight-forward, by limiting the access to which entities can call the [`WildcatMarketController::updateLenderAuthorization()` function](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketController.sol#L182-L190); either only allow the Borrower to call it, or create a type of whitelist of valid actors who are capable of updating the lender’s authorization on the Markets. In this way, the Lenders won’t be capable of granting the `WithdrawOnly` Role to any account they want to; thus, they won’t be able even to attempt to escape the sanctions.

**WildcatMarketController.sol**
```solidity
    - function updateLenderAuthorization(address lender, address[] memory markets) external {
    + function updateLenderAuthorization(address lender, address[] memory markets) external onlyAuthorizedEntities(){
        for (uint256 i; i < markets.length; i++) {
          address market = markets[i];
          if (!_controlledMarkets.contains(market)) {
            revert NotControlledMarket();
          }
          WildcatMarket(market).updateAccountAuthorization(lender, _authorizedLenders.contains(lender));
        }
      }

    modifier onlyAuthorizedEntities() {
        require(msg.sender == <authorizedEntities>, "you are not allowed sir");
        _;
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability allows alender who has been flagged as sanctioned by the Chainalysis oracle to bypass the market’s blacklisting mechanism and still withdraw funds. The root cause is the public WildcatMarketController.updateLenderAuthorization function, which any address can call. This function iterates over a list of markets and forwards a boolean flag derived from the controller’s internal _authorizedLenders set to WildcatMarket.updateAccountAuthorization. When the lender address is not present in _authorizedLenders, the flag is false, and the market’s updateAccountAuthorization routine interprets a false _isAuthorized value as a command to assign the WithdrawOnly role to the supplied account. Because the caller can choose any target address, a sanctioned lender can first transfer all of its MarketTokens to fresh accounts that hold no role, then invoke updateLenderAuthorization with those accounts as the "lender" argument. The market will grant each of those accounts the WithdrawOnly role, which permits only withdrawals and no further deposits. The lender can then queue and execute withdrawal requests from any of the newly funded accounts, effectively escaping the sanction. This attack can be performed after the lender’s original address has been marked as sanctioned but before the nukeFromOrbit function fully blocks the account, or even after nukeFromOrbit because the tokens have already been moved. From a user perspective the expected behaviour is that a sanctioned account becomes unable to move funds; instead the user sees their tokens disappear from the original address yet remains able to pull the same amount out of other addresses, leading to confusion and a false sense of security that the protocol is enforcing sanctions. The impact is that the protocol’s compliance enforcement is broken, allowing malicious or sanctioned actors to extract value that should have been frozen, potentially resulting in financial loss and reputational damage. The issue was discovered during a security audit that examined the interaction between the sanctions sentinel and the controller’s authorization update logic; it is subtle because the false flag is not an error but is interpreted as a legitimate role change, making it easy to overlook during testing. To remediate, the updateLenderAuthorization function should be restricted to a trusted caller (e.g., only the borrower or a whitelisted admin) and the market’s updateAccountAuthorization logic should not automatically grant WithdrawOnly on a false flag without explicit revocation semantics. In other words, the protocol must enforce proper access control on role‑changing functions and separate the concepts of “authorized” and “withdraw‑only” to prevent arbitrary role escalation by sanctioned lenders.
