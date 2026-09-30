---
id: 14221
severity: "High"
---

# Malicious Users Can Exploit Residual Allowance To Steal Assets

## Description

A depositor cannot have any residual allowance after depositing to the vault because the tokens can be stolen by anyone.

Loss of assets for users as a malicious user could utilise the `baseVault` contract to exploit the user’s residual allowance to steal their assets.

## Proof of Concept

Assume that Alice has finished deploying the vault, and she would like to deposit her ERC20, ERC721, and ERC1155 tokens to the vault. She currently holds the following assets in her wallet

  * `1000` XYZ ERC20 tokens
  * APE #1 ERC721 NFT, APE #2 ERC721 NFT, APE #3 ERC721 NFT,
  * `1000` ABC ERC1155 tokens

Thus, she sets up the necessary approval to grant [`baseVault`](https://github.com/code-423n4/2022-07-fractional/blob/8f2697ae727c60c93ea47276f8fa128369abfe51/src/modules/protoforms/BaseVault.sol#L17) contract the permission to transfer her tokens to the vault.

```solidity
erc20.approve(address(baseVault), type(uint256).max);
erc721.setApprovalForAll(address(baseVault), true);
erc1155.setApprovalForAll(address(baseVault), true);
```

Alice decided to deposit `50` XYZ ERC20 tokens, APE #1 ERC721 NFT, and `50` ABC tokens to the vault by calling `baseVault.batchDepositERC20`, `baseVault.batchDepositERC721`, and `baseVault.batchDepositERC1155` as shown below:

```solidity
baseVault.batchDepositERC20(alice.addr, vault, [XYZ.addr], [50])
baseVault.batchDepositERC721(alice.addr, vault, [APE.addr], [#1])
baseVault.batchDepositERC1155(alice.addr, vault, [ABC.addr], [#1], [50], "")
```

An attacker notices that there is residual allowance left on the `baseVault`, thus the attacker executes the following transactions to steal Alice’s assets and send them to the attacker’s wallet address.

```solidity
baseVault.batchDepositERC20(alice.addr, attacker.addr, [XYZ.addr], [950])
baseVault.batchDepositERC721(alice.addr, attacker.addr, [APE.addr, APE.addr], [#2, #3])
baseVault.batchDepositERC1155(alice.addr, attacker.addr, [ABC.addr], [#1], [950], "")
```

```solidity
function batchDepositERC20(
    address _from,
    address _to,
    address[] calldata _tokens,
    uint256[] calldata _amounts
) external {
    for (uint256 i = 0; i < _tokens.length; ) {
        IERC20(_tokens[i]).transferFrom(_from, _to, _amounts[i]);
        unchecked {
            ++i;
        }
    }
}

function batchDepositERC721(
    address _from,
    address _to,
    address[] calldata _tokens,
    uint256[] calldata _ids
) external {
    for (uint256 i = 0; i < _tokens.length; ) {
        IERC721(_tokens[i]).safeTransferFrom(_from, _to, _ids[i]);
        unchecked {
            ++i;
        }
    }
}

function batchDepositERC1155(
    address _from,
    address _to,
    address[] calldata _tokens,
    uint256[] calldata _ids,
    uint256[] calldata _amounts,
    bytes[] calldata _datas
) external {
    unchecked {
        for (uint256 i = 0; i < _tokens.length; ++i) {
            IERC1155(_tokens[i]).safeTransferFrom(
                _from,
                _to,
                _ids[i],
                _amounts[i],
                _datas[i]
            );
        }
    }
}
```

## Recommendation

It is recommended to only allow the `baseVault.batchDepositERC20`, `baseVault.batchDepositERC721`, and `baseVault.batchDepositERC1155` functions to pull tokens from the caller (`msg.sender`).

Considering updating the affected functions to remove the `from` parameter, and use `msg.sender` instead.

```solidity
function batchDepositERC20(
    address _to,
    address[] calldata _tokens,
    uint256[] calldata _amounts
) external {
    for (uint256 i = 0; i < _tokens.length; ) {
        IERC20(_tokens[i]).transferFrom(msg.sender, _to, _amounts[i]);
        unchecked {
            ++i;
        }
    }
}

function batchDepositERC721(
    address _to,
    address[] calldata _tokens,
    uint256[] calldata _ids
) external {
    for (uint256 i = 0; i < _tokens.length; ) {
        IERC721(_tokens[i]).safeTransferFrom(msg.sender, _to, _ids[i]);
        unchecked {
            ++i;
        }
    }
}

function batchDepositERC1155(
    address _to,
    address[] calldata _tokens,
    uint256[] calldata _ids,
    uint256[] calldata _amounts,
    bytes[] calldata _datas
) external {
    unchecked {
        for (uint256 i = 0; i < _tokens.length; ++i) {
            IERC1155(_tokens[i]).safeTransferFrom(
                msg.sender,
                _to,
                _ids[i],
                _amounts[i],
                _datas[i]
            );
        }
    }
}
```

Confirmed, we will be addressing this issue!

Anyone who approved the BaseVault can have their tokens stolen. Agree this is high risk.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of an authorization flaw in the batch deposit functions of the BaseVault contract that allow any caller to specify an arbitrary source address (_from) when pulling tokens via ERC20.transferFrom, ERC721.safeTransferFrom, or ERC1155.safeTransferFrom. When a user grants the vault an unlimited allowance (e.g., by calling approve or setApprovalForAll) and then performs a deposit that consumes only a portion of that allowance, a residual allowance remains on the token contract. Because the batch functions do not verify that the _from argument matches the transaction sender, a malicious actor can invoke the same functions with the victim’s address as _from and direct the tokens to an attacker‑controlled address. The attack proceeds step‑by‑step: (1) Victim Alice approves the BaseVault for all of her ERC20, ERC721, and ERC1155 tokens; (2) Alice deposits a small amount (50 tokens, one NFT, 50 units) using the batchDeposit functions, leaving a large unused allowance; (3) Attacker observes the remaining allowance and calls batchDepositERC20, batchDepositERC721, and batchDepositERC1155 with _from set to Alice’s address and _to set to the attacker’s address, transferring the residual balances (950 ERC20, two NFTs, 950 ERC1155 units). The impact is a complete loss of the victim’s assets – balances appear to drop to zero, refunds are missing, and the user receives no tokens despite having approved the vault. This flaw can be triggered whenever a user approves the vault with a high or unlimited allowance and does not consume the entire allowance in a single deposit. It affects any role that can grant allowance to the vault, including regular users and contract owners, and compromises the trust model of the protocol. The issue was discovered during a security audit that examined the contract’s token handling logic and identified that the _from parameter was not restricted. The problem is subtle because the transaction looks like a regular deposit and the UI does not expose the remaining allowance; therefore the theft can occur without obvious warning signs. To remediate, the functions should be rewritten to pull tokens only from msg.sender, removing the external _from parameter, or adding a strict access control that enforces _from == msg.sender. This change aligns the contract with the principle of least privilege and eliminates the residual allowance attack vector, restoring proper accounting and preventing unauthorized asset extraction.
