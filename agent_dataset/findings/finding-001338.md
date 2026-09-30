---
id: 1338
severity: "High"
---

# Possibility to drain SavingsAccount contract assets

## Description

A malicious actor can manipulate switchStrategy() function in a way to withdraw tokens that are locked in SavingsAccount contract (the risk severity should be reviewed)

## Proof of Concept

Firstly an attacker need to deploy a rogue strategy contract implementing IYield.getSharesForTokens() and IYield.unlockTokens() functions and calling switchStrategy() with _currentStrategy = ROGUE _CONTRACT_ ADDRESS (_newStrategy can be any valid strategy e.g. NoYield)

```solidity
    require(_amount != 0, 'SavingsAccount::switchStrategy Amount must be greater than zero');
```

Bypass this check by setting _amount > 0, since it will be overwritten in line <https://github.com/code-423n4/2021-12-sublime/blob/main/contracts/SavingsAccount/SavingsAccount.sol#L162>

```solidity
    _amount = IYield(_currentStrategy).getSharesForTokens(_amount, _token);
```

getSharesForTokens() should be implemented to always return 0, hence to bypass the overflow in lines <https://github.com/code-423n4/2021-12-sublime/blob/main/contracts/SavingsAccount/SavingsAccount.sol#L164-L167>

```solidity
    balanceInShares[msg.sender][_token][_currentStrategy] = balanceInShares[msg.sender][_token][_currentStrategy].sub(
    _amount,
    'SavingsAccount::switchStrategy Insufficient balance'
    );
```

since balanceInShares[msg.sender][_token][_currentStrategy] == 0 and 0-0 will not overflow

The actual amount to be locked is saved in line <https://github.com/code-423n4/2021-12-sublime/blob/main/contracts/SavingsAccount/SavingsAccount.sol#L169>

```solidity
    uint256 _tokensReceived = IYield(_currentStrategy).unlockTokens(_token, _amount);
```

the rouge unlockTokens() can check asset balance of the contract and return the full amount

After that some adjustment are made to set approval for the token or to handle native assets case <https://github.com/code-423n4/2021-12-sublime/blob/main/contracts/SavingsAccount/SavingsAccount.sol#L171-L177>

```solidity
    uint256 _ethValue;
    if (_token != address(0)) {
        IERC20(_token).safeApprove(_newStrategy, _tokensReceived);
    } else {
        _ethValue = _tokensReceived;
    }
    _amount = _tokensReceived;
```

Finally the assets are locked in the locked strategy and shares are allocated on attackers acount <https://github.com/code-423n4/2021-12-sublime/blob/main/contracts/SavingsAccount/SavingsAccount.sol#L179-L181>

```solidity
    uint256 _sharesReceived = IYield(_newStrategy).lockTokens{value: _ethValue}(address(this), _token, _tokensReceived);
    
    balanceInShares[msg.sender][_token][_newStrategy] = balanceInShares[msg.sender][_token][_newStrategy].add(_sharesReceived);
```

Proof of Concept

```solidity
    import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
    
    contract Attacker{
        function getSharesForTokens(uint256 amount, address token) external payable  returns(uint256){
            return 0;
        }
        function unlockTokens(address token, uint256 amount) external payable returns(uint256){
            uint256 bal;
            if(token == address(0))
                bal = msg.sender.balance;
            else
                bal = IERC20(token).balanceOf(msg.sender);
            return bal;
        }
    }
```

## Recommendation

Add a check for _currentStrategy to be from strategy list like the one in line <https://github.com/code-423n4/2021-12-sublime/blob/main/contracts/SavingsAccount/SavingsAccount.sol#L159>

```solidity
    require(IStrategyRegistry(strategyRegistry).registry(_newStrategy), 'SavingsAccount::_newStrategy do not exist');
```

The savings account contract doesn’t hold any tokens, so it is not possible to lock tokens in a new strategy, hence this attack will not work. Nevertheless it is something we will explore further to limit unexpected state changes

Based on the review of the warden I believe this is a valid attack path. This line would need to change to the amount of tokens that are to be “stolen” but otherwise this does seem accurate. 

```solidity
    bal = IERC20(token).balanceOf(msg.sender);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the SavingsAccount contract’s switchStrategy function, which enables a user to move a token balance from one yield‑earning strategy to another. The function does not verify that the _currentStrategy argument belongs to the registered strategy list, allowing an attacker to supply an arbitrary contract that pretends to be a strategy. Because the contract trusts the strategy’s implementation of IYield.getSharesForTokens and IYield.unlockTokens, a malicious strategy can manipulate the internal accounting. An attacker can deploy a rogue strategy whose getSharesForTokens always returns zero, causing the subtraction of shares to succeed as 0‑0 does not underflow. The attacker then supplies a non‑zero _amount, which is overwritten with the zero shares value, and the contract proceeds to call unlockTokens on the rogue contract. The rogue unlockTokens implementation can read the SavingsAccount’s token balance (or ether balance) and return the full amount, effectively withdrawing all assets that were thought to be locked. After the assets are released, the function approves the new strategy (or transfers ether) and re‑locks the tokens, crediting the attacker’s address with shares in the new strategy. From the user’s perspective the funds they deposited disappear; the UI may show a zero balance or a missing refund, while the attacker ends up with the full token amount. This attack can be triggered by any user who can call switchStrategy, meaning all token holders and the protocol’s overall liquidity are at risk. The issue was uncovered during a manual code audit that highlighted the missing registry check for the current strategy and the reliance on external contract callbacks for critical accounting. The flaw is subtle because the function appears to perform a safe migration between strategies, and the subtraction of zero shares passes unnoticed, while the token transfer logic is hidden inside the external strategy. To remediate, the contract should enforce that both _currentStrategy and _newStrategy are registered in the strategy registry, validate that getSharesForTokens returns a value consistent with the caller’s actual share balance, and ensure that unlockTokens cannot release more tokens than were previously locked. Adding these checks restores the intended invariants that a user’s share balance accurately reflects the underlying token amount, preventing arbitrary draining of assets.
